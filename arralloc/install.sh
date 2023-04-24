# just needs to be run once to get all the allocators installed
SCRIPT_LOC=$(realpath $(dirname $0))

mkdir -p __tmp_alloc_install
cd __tmp_alloc_install

# jemalloc
git clone https://github.com/jemalloc/jemalloc.git jemalloc
cd jemalloc
./autogen.sh
make
make install
cd ..

# # tcmalloc
# # command differs for different distros
# if [ -x "$(command -v apt-get)" ]; then
#     sudo apt-get -y install libgoogle-perftools-dev
# elif [ -x "$(command -v yum)" ]; then
#     sudo yum -y install gperftools-devel
# fi

# # tcmalloc manual approach 
# git clone https://github.com/google/tcmalloc.git tcmalloc
# cd tcmalloc
# bazel test //tcmalloc/...  # doesn't work

# hoard
git clone https://github.com/emeryberger/Hoard hoard
cd hoard/src
make
cd ../..
