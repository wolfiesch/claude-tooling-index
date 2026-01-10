cmake_minimum_required(VERSION 3.10)
project(tooling-index-hook CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find SQLite3
find_package(SQLite3 REQUIRED)

# Build hook binary
add_executable(post_tool_use_tooling post_tool_use_tooling.cpp)

target_link_libraries(post_tool_use_tooling PRIVATE SQLite::SQLite3)

# Optimization for release builds
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    target_compile_options(post_tool_use_tooling PRIVATE -O3 -DNDEBUG)
endif()

# Install to ~/.claude/hooks/
install(TARGETS post_tool_use_tooling
        RUNTIME DESTINATION "$ENV{HOME}/.claude/hooks"
        PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
                    GROUP_READ GROUP_EXECUTE
                    WORLD_READ WORLD_EXECUTE)
