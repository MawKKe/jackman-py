
cmake_minimum_required(VERSION 3.16)

project(my-project-fixme)



add_library(foo
    foo.cc
)
#
target_include_directories(foo
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
)

add_executable(main-exe
    main.cc
)


target_link_libraries(main-exe
    foo
    bar
    baz
)

add_subdirectory(very/deep/path/way/in/the/woods/i/think/i/saw/the/pope/back/there)

