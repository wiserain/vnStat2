#!/bin/sh

# detecting the platform
os="$(uname)"
case $os in
    Linux)
        os='linux'
        ;;
    *)
        echo 'os not supported'
        exit 2
        ;;
esac

arch="$(uname -m)"
case $arch in
    x86_64|amd64)
        arch='amd64'
        ;;
    aarch64)
        arch='arm64'
        ;;
    arm*)
        arch='arm'
        ;;
    *)
        echo 'architecture not supported'
        exit 2
        ;;
esac

if [ -f /usr/bin/apt ]; then
    distro='ubuntu'
    os_ver=$(cat /etc/lsb-release | grep DISTRIB_RELEASE | cut -d= -f2)
elif [ -f /sbin/apk ]; then
    distro='alpine'
    os_ver=$(head -n1 /etc/apk/repositories | sed -e 's/.*\/v\(.*\)\/.*/\1/g')
else
    echo 'os distro not supported'
    exit 2
fi

if [ $distro = "ubuntu" ]; then
    # wait until apt-get not used by other process
    while ps -opid= -C apt-get > /dev/null; do sleep 1; done
    # apt-get update if never done during the past 24 hours
    [ ! -d /var/lib/apt/lists/partial ] && apt-get update -yqq
    [ -z "$(find -H /var/lib/apt/lists -maxdepth 0 -mtime -1)" ] && apt-get update -yqq 

    echo ""
    echo "===================================================================="
    echo "Installing vnStat ..."
    echo "===================================================================="
    echo ""
    apt-get install -y --no-install-recommends \
        vnstat=${1}*
elif [ $distro = "alpine" ]; then
    # delete existing vnstat
    apk del --purge --no-cache vnstat

    echo ""
    echo "===================================================================="
    echo "Installing vnStat from package repository ..."
    echo "===================================================================="
    echo ""
    apk add --no-cache vnstat~="${1}" >/dev/null 2>&1
    if [ $? != 0 ]; then
        echo ""
        echo "===================================================================="
        echo "Building vnStat from source ..."
        echo "===================================================================="
        echo ""
        apk add --no-cache --virtual=vnstat-build \
            sqlite-dev \
            gd-dev \
            build-base \
            coreutils \
            libjpeg-turbo-dev \
            libpng-dev

        tmpdir=$(mktemp -d)
        cd "$tmpdir" || exit

        wget http://humdi.net/vnstat/vnstat-"${1}".tar.gz -O - | tar -xzvf - --strip-components=1

        # https://github.com/alpinelinux/aports/blob/master/community/vnstat/APKBUILD
        ./configure \
            --prefix=/usr \
            --sysconfdir=/etc \
            --mandir=/usr/share/man \
            --infodir=/usr/share/info

        make && make install

        apk del --purge --no-cache vnstat-build
        apk add --no-cache libgd

        rm -rf "$tmpdir"
    fi
fi

# checking installation
command -v vnstat >/dev/null 2>&1 && \
    {
        echo ""
        echo "===================================================================="
        echo "$(vnstat --version)"
        echo "===================================================================="
        echo ""
    } || \
    {
        echo ""
        echo "===================================================================="
        echo "Something went wrong !!!"
        echo "===================================================================="
        echo ""
    }
