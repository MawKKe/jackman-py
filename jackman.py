#!/usr/bin/env python3

import sys
import shlex
import typing as t
import hashlib
import subprocess
import time
import os
from pathlib import Path

MAX_ARGUMENT_LENGTH: int = 240
HEX_DIGEST_SIZE_BYTES: int = 8

class Config:
    def __init__(self, cwd: Path, prefix: Path):
        self.cwd = Path(cwd)
        self.prefix = Path(prefix)
        self.rewrite_rsp = False


def hash_dir(path: Path) -> Path:
    return Path(hashlib.blake2b(bytes(path), digest_size=HEX_DIGEST_SIZE_BYTES).hexdigest())


def hijack(args: t.List[str], config: Config) -> t.List[str]:
    (config.cwd / config.prefix).mkdir(parents=True, exist_ok=True)

    def simple_hash_file(file_path: Path) -> Path:
        file_path = Path(file_path)
        return simple_hash_dir(file_path.parent) / file_path.name

    def simple_hash_dir(file_path: Path) -> Path:
        file_path = Path(file_path)
        return config.prefix / hash_dir(file_path)

    def hash_rsp_contents(infile: Path) -> Path:
        infile = Path(infile)
        outfile = infile.parent / f'_jacked_{infile.name}'

        lines = (Path(line.strip()) for line in infile.read_text().splitlines())
        aliased = [str(simple_hash_file(file_path)) for file_path in lines]
        outfile.write_text('\n'.join(aliased))
        assert all(len(path) <= MAX_ARGUMENT_LENGTH for path in aliased), \
               ('modified response file contains too long filenames even '
                f'after hashing/aliasing, see {str(outfile)}')

        # reroute original rsp argument to the new one
        # NOTE: this path itself has not yet been hashed
        return outfile

    n = len(args)
    i = 0
    while i < n:
        # name of the game: attempt to recognize when file paths are passed as argument,
        # and hash-alias those paths with symlinks, then pass the alias in place of the
        # original argument.
        # Default fallback is to pass all unrecognized arguments as-is.
        #
        # This is merely a heuristic, and may fail in some unforeseen cases. However,
        # it should be easy to augment those cases when needed. Due to operaiting principle
        # (symlinks to original dirs), the compilation should succeed just fine even if
        # all file paths are not captured

        curr_arg = args[i]
        next_arg = None if i+1 >= n else args[i+1]

        is_rsp = False
        is_file = True

        rpath = '-Wl,-rpath,'

        if len(curr_arg) < 2:
            yield curr_arg
            i += 1
            continue

        if curr_arg in ['-c', '-o']:
            yield curr_arg
            is_file = True
            if not next_arg:
                break  # out of args
            curr_arg = next_arg
            i += 2
        elif (opt := curr_arg[:2]) in ['-I', '-L']:
            # handles ['-I', 'foo/bar'] and ['-Ifoo/bar'] equally
            yield opt
            is_file = False
            if remainder := curr_arg[2:]:
                curr_arg = remainder
                i += 1
            elif next_arg:
                curr_arg = next_arg
                i += 2
            else:
                # out of args
                break
        elif curr_arg.startswith(rpath):
            reldir = Path(curr_arg[len(rpath):])
            yield rpath + str(config.cwd / simple_hash_dir(reldir))
            i += 1
            continue
        elif curr_arg[0] == '@':
            if not curr_arg.endswith('.rsp'):
                # likely some rpath argument, not response file, pass as-is
                yield curr_arg
                i += 1
                continue

            is_rsp = True

            # NOTE: we must also hash the rsp file path, but _without_ the @ prefix char
            path = Path(curr_arg[1:])

            if config.rewrite_rsp:
                curr_arg = hash_rsp_contents(path)
            else:
                curr_arg = path

            is_file = True
            i += 1
        elif Path(curr_arg).suffix in ['.a', '.so', '.dylib', '.lib']:
            # positional argument, usually libraries passed during linking step
            # Paths to these usually do not have the 'CMakeFiles' component in them
            is_file = True
            i += 1
        elif 'CMakeFiles' in curr_arg:
            if Path(curr_arg).suffix not in ['.d', '.o', '.dep']:
                # There might be omissions, add known extensions to the above list if needed
                raise RuntimeError(f'Uknown CMakeFiles file type: {curr_arg}?')
            i += 1
        else:
            # Anything our heuristic did not recognize is passed as-is
            yield curr_arg
            i += 1
            continue

        # from here onwards, we assume current argument is a file or directory path that
        # needs to be shortened

        curr_arg = Path(curr_arg)

        if is_file:
            original_dir = curr_arg.parent
            alias_dir = simple_hash_dir(original_dir)
            rewritten = ['', '@'][is_rsp] + str(alias_dir / curr_arg.name)
        else:
            original_dir = curr_arg
            alias_dir = simple_hash_dir(original_dir)
            rewritten = str(alias_dir)

        if original_dir.is_absolute():
            target = original_dir
        else:
            target = config.cwd / original_dir

        # It is possible that multiple processes want attempt to create this same alias
        # symlink concurrently; use atomicity of rename to prevent race conditions
        # from ruining our day
        tmp_link = alias_dir.with_name(str(hash(alias_dir)) + str(hash(curr_arg)))
        os.symlink(target, config.cwd / tmp_link)
        os.rename(config.cwd / tmp_link, config.cwd / alias_dir)

        yield rewritten


def main(argv):
    a = time.perf_counter()

    # Typically build tooling changes the directory to the build directory
    # before compiler is called; this mean the prefix can be relative and thus
    # the symlinks created by jackman end up in the output directory also
    # (which is desirable, makes for easy cleaning)
    prefix = os.getenv('JACKMAN_PREFIX', '_jackman')

    assert len(prefix) > 1, f'JACKMAN_PREFIX is too short, got: {prefix}'

    config = Config(
        cwd=Path('.').resolve(),
        prefix=Path(prefix),
    )

    cmd, *args = argv[1:]

    cmd_name = Path(cmd).name

    cmds_needing_rsp_rewrite = []  # FIXME

    # Force rewriting of response file contents. You might want to
    # enable/disable this depending on which tool is being wrapped.
    rewrite_force = os.getenv('JACKMAN_REWRITE_RSP', False)

    config.rewrite_rsp = cmd_name in cmds_needing_rsp_rewrite or rewrite_force

    modified_args = list(hijack(args, config))

    for i, arg in enumerate(modified_args):
        # Last safety check - prevent accidentally passing invalid args
        # The inner command might not even handle oversized args gracefully.
        # We want to avoid silent crashes at all costs
        if len(arg) <= MAX_ARGUMENT_LENGTH:
            continue
        # The whole point of this script is to re-route long paths to shorter aliases,
        # so if this check trips up with your build, upgrade the heuristic in 'hijack()'
        # so it will be handled appropriately.
        raise RuntimeError(f'ERROR: argument "{arg}" is {len(arg)} characters long, max: {MAX_ARGUMENT_LENGTH}')

    new_argv = [cmd] + modified_args

    b = time.perf_counter()

    if os.getenv('JACKMAN_VERBOSE', False):
        print('>>> [jackman] REWRITE:', shlex.join(new_argv), file=sys.stderr)

    if os.getenv('JACKMAN_DEBUG_PERF', False):
        print(f'>>> [jackman] PERF: {(b-a)*1000:.2f} ms', file=sys.stderr)

    p = subprocess.run(new_argv)

    return p.returncode

if __name__ == '__main__':
    sys.exit(main(sys.argv))
