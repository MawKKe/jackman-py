add_library(bar STATIC bar.cc)

target_include_directories(bar PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

add_library(baz SHARED baz.cc)

target_include_directories(baz PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
