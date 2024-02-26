import jackman
from pathlib import Path


def test_simple(tmp_path):
    config = jackman.Config(prefix='_pytest', cwd=tmp_path.resolve())
    args = [
        'gcc', '-Wall', '-Wextra',
        '-c', 'foo/bar/baz.c',
        '-Ipath/to/include',
        '-o', 'myexe'
    ]
    expect = [
        'gcc', '-Wall', '-Wextra',
        '-c', '_pytest/ad884951a73c822f/baz.c',  # hash(b'foo/bar') = ad88...822f
        '-I', '_pytest/b9e95d2b2621ea80',        # hash(b'path/to') = b9e9...ea80
        '-o', '_pytest/f01d79cfb6e37084/myexe'   # hash(b'.')       = f01d...7084
    ]
    res = list(jackman.hijack(args, config))

    assert len(res) == 9
    assert res == expect

    fs = list(tmp_path.rglob('_pytest/*'))
    assert len(fs) == 3
    assert (tmp_path / '_pytest/ad884951a73c822f').is_symlink()
    assert (tmp_path / '_pytest/b9e95d2b2621ea80').is_symlink()
    assert (tmp_path / '_pytest/f01d79cfb6e37084').is_symlink()

    assert (tmp_path / '_pytest/ad884951a73c822f').readlink().relative_to(tmp_path) == Path('foo/bar')
    assert (tmp_path / '_pytest/b9e95d2b2621ea80').readlink().relative_to(tmp_path) == Path('path/to/include')
    assert (tmp_path / '_pytest/f01d79cfb6e37084').readlink().relative_to(tmp_path) == Path('.')
