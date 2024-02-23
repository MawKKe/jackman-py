JACKMAN := $(abspath jackman.py)

test:
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
	cmake --build out --verbose --parallel 1
