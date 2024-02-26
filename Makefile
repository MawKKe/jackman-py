JACKMAN := $(abspath jackman.py)

test:
	pytest test_jackman.py -v

test-with-cmake:
	rm -rf out
	${MAKE} configure
	${MAKE} build

configure:
	cmake -B out -S dummy_cmake_proj -G Ninja \
		-DCMAKE_CXX_COMPILER_LAUNCHER=${JACKMAN} \
		-DCMAKE_CXX_LINKER_LAUNCHER=${JACKMAN}

configure-nowrap:
	cmake -B out-nowrap -S dummy_cmake_proj -G Ninja

build:
	env JACKMAN_VERBOSE=1 JACKMAN_DEBUG_PERF=1 cmake --build out --verbose --parallel 1
