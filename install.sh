#!/bin/sh
# shellcheck shell=dash

# This is just a little script that can be downloaded from the internet to
# install poetry. It just does platform detection, downloads the distribution
# and installs it.

# It runs on Unix shells like {a,ba,da,k,z}sh. It uses the common `local`
# extension. Note: Most shells limit `local` to 1 var per line, contra bash.

if [ "$KSH_VERSION" = 'Version JM 93t+ 2010-03-05' ]; then
    # The version of ksh93 that ships with many illumos systems does not
    # support the "local" extension.  Print a message rather than fail in
    # subtle ways later on:
    echo 'this script does not work with this ksh93 version; please try bash!' >&2
    exit 1
fi

set -u

_ansi_escapes_are_valid=false
if [ -t 2 ]; then
    if [ "${TERM+set}" = 'set' ]; then
        case "$TERM" in
            xterm*|rxvt*|urxvt*|linux*|vt*)
                _ansi_escapes_are_valid=true
            ;;
        esac
    fi
fi

POETRYBIN_REPO="${POETRYBIN_REPO:-gi0baro/poetry-bin}"

main() {
    downloader --check
    need_cmd uname
    need_cmd mktemp
    need_cmd mkdir
    need_cmd rm
    need_cmd rmdir
    need_cmd tar

    get_architecture || return 1
    local _arch="$RETVAL"
    assert_nz "$_arch" "arch"

    local _dir
    _dir="$(mktemp -d 2>/dev/null || ensure mktemp -d -t poetry-bin)"

    local _path_prefix="/usr"
    local _path_pre
    local _path_local
    local _path_dest

    local _path_bin="$(get_binpath)"
    if [ -z "$_path_bin" ]; then
        err "Cannot resolve local path for installation"
    fi

    _path_pre="$(dirname "$_path_bin")"
    _path_local="$_path_pre/poetry-bin-releases"

    info 'checking lastest available release..'
    local _latest=$(fetcher https://api.github.com/repos/$POETRYBIN_REPO/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -z $_latest ]; then
        err "Cannot resolve latest release"
    fi

    info "downloading distribution $_latest.."
    local _file="poetry-bin-$_latest-$_arch.tar.gz"
    local _url="https://github.com/${POETRYBIN_REPO}/releases/download/${_latest}/${_file}"

    ensure downloader "$_url" "$_dir/$_file" "$_arch"

    _path_dest="$_path_local/$_latest"
    info "installing distribution to $_path_dest.."

    ignore rm -rf "$_path_dest"
    ensure mkdir -p "$_path_dest"
    ensure tar xzf "$_dir/$_file" --directory "$_path_dest"
    ignore rm "$_path_bin/poetry"
    ensure ln -s "$_path_dest/poetry" "$_path_bin/poetry"

    ignore rm "$_dir/$_file"
    ignore rmdir "$_dir"

    info "correctly installed poetry to $_path_bin/poetry"
}

get_binpath() {
    local _path_prefix="/usr"

    echo "$PATH" | tr ':' '\n' | while read _bin_path; do
        if echo "$_bin_path" | grep -q $_path_prefix; then
            echo "$_bin_path"
            break
        fi
    done
}

get_bitness() {
    need_cmd head
    # Architecture detection without dependencies beyond coreutils.
    # ELF files start out "\x7fELF", and the following byte is
    #   0x01 for 32-bit and
    #   0x02 for 64-bit.
    # The printf builtin on some shells like dash only supports octal
    # escape sequences, so we use those.
    local _current_exe_head
    _current_exe_head=$(head -c 5 /proc/self/exe )
    if [ "$_current_exe_head" = "$(printf '\177ELF\001')" ]; then
        echo 32
    elif [ "$_current_exe_head" = "$(printf '\177ELF\002')" ]; then
        echo 64
    else
        err "unknown platform bitness"
    fi
}

get_endianness() {
    local cputype=$1
    local suffix_eb=$2
    local suffix_el=$3

    # detect endianness without od/hexdump, like get_bitness() does.
    need_cmd head
    need_cmd tail

    local _current_exe_endianness
    _current_exe_endianness="$(head -c 6 /proc/self/exe | tail -c 1)"
    if [ "$_current_exe_endianness" = "$(printf '\001')" ]; then
        echo "${cputype}${suffix_el}"
    elif [ "$_current_exe_endianness" = "$(printf '\002')" ]; then
        echo "${cputype}${suffix_eb}"
    else
        err "unknown platform endianness"
    fi
}

get_architecture() {
    local _ostype _cputype _bitness _arch _clibtype
    _ostype="$(uname -s)"
    _cputype="$(uname -m)"
    _clibtype="gnu"

    if [ "$_ostype" = Linux ]; then
        if [ "$(uname -o)" = Android ]; then
            _ostype=Android
        fi
        if ldd --version 2>&1 | grep -q 'musl'; then
            _clibtype="musl"
        fi
    fi

    if [ "$_ostype" = Darwin ] && [ "$_cputype" = i386 ]; then
        # Darwin `uname -m` lies
        if sysctl hw.optional.x86_64 | grep -q ': 1'; then
            _cputype=x86_64
        fi
    fi

    if [ "$_ostype" = SunOS ]; then
        # Both Solaris and illumos presently announce as "SunOS" in "uname -s"
        # so use "uname -o" to disambiguate.  We use the full path to the
        # system uname in case the user has coreutils uname first in PATH,
        # which has historically sometimes printed the wrong value here.
        if [ "$(/usr/bin/uname -o)" = illumos ]; then
            _ostype=illumos
        fi

        # illumos systems have multi-arch userlands, and "uname -m" reports the
        # machine hardware name; e.g., "i86pc" on both 32- and 64-bit x86
        # systems.  Check for the native (widest) instruction set on the
        # running kernel:
        if [ "$_cputype" = i86pc ]; then
            _cputype="$(isainfo -n)"
        fi
    fi

    case "$_ostype" in

        Android)
            _ostype=linux-android
            ;;

        Linux)
            _ostype=unknown-linux-$_clibtype
            _bitness=$(get_bitness)
            ;;

        FreeBSD)
            _ostype=unknown-freebsd
            ;;

        NetBSD)
            _ostype=unknown-netbsd
            ;;

        DragonFly)
            _ostype=unknown-dragonfly
            ;;

        Darwin)
            _ostype=apple-darwin
            ;;

        illumos)
            _ostype=unknown-illumos
            ;;

        MINGW* | MSYS* | CYGWIN*)
            _ostype=pc-windows-gnu
            ;;

        *)
            err "unrecognized OS type: $_ostype"
            ;;

    esac

    case "$_cputype" in

        i386 | i486 | i686 | i786 | x86)
            _cputype=i686
            ;;

        xscale | arm)
            _cputype=arm
            if [ "$_ostype" = "linux-android" ]; then
                _ostype=linux-androideabi
            fi
            ;;

        armv6l)
            _cputype=arm
            if [ "$_ostype" = "linux-android" ]; then
                _ostype=linux-androideabi
            else
                _ostype="${_ostype}eabihf"
            fi
            ;;

        armv7l | armv8l)
            _cputype=armv7
            if [ "$_ostype" = "linux-android" ]; then
                _ostype=linux-androideabi
            else
                _ostype="${_ostype}eabihf"
            fi
            ;;

        aarch64 | arm64)
            _cputype=aarch64
            ;;

        x86_64 | x86-64 | x64 | amd64)
            _cputype=x86_64
            ;;

        mips)
            _cputype=$(get_endianness mips '' el)
            ;;

        mips64)
            if [ "$_bitness" -eq 64 ]; then
                # only n64 ABI is supported for now
                _ostype="${_ostype}abi64"
                _cputype=$(get_endianness mips64 '' el)
            fi
            ;;

        ppc)
            _cputype=powerpc
            ;;

        ppc64)
            _cputype=powerpc64
            ;;

        ppc64le)
            _cputype=powerpc64le
            ;;

        s390x)
            _cputype=s390x
            ;;
        riscv64)
            _cputype=riscv64gc
            ;;
        *)
            err "unknown CPU type: $_cputype"

    esac

    # Detect 64-bit linux with 32-bit userland
    if [ "${_ostype}" = unknown-linux-gnu ] && [ "${_bitness}" -eq 32 ]; then
        case $_cputype in
            x86_64)
                _cputype=i686
                ;;
            mips64)
                _cputype=$(get_endianness mips '' el)
                ;;
            powerpc64)
                _cputype=powerpc
                ;;
            aarch64)
                _cputype=armv7
                if [ "$_ostype" = "linux-android" ]; then
                    _ostype=linux-androideabi
                else
                    _ostype="${_ostype}eabihf"
                fi
                ;;
            riscv64gc)
                err "riscv64 with 32-bit userland unsupported"
                ;;
        esac
    fi

    # Detect armv7 but without the CPU features Rust needs in that build,
    # and fall back to arm.
    if [ "$_ostype" = "unknown-linux-gnueabihf" ] && [ "$_cputype" = armv7 ]; then
        if ensure grep '^Features' /proc/cpuinfo | grep -q -v neon; then
            # At least one processor does not have NEON.
            _cputype=arm
        fi
    fi

    _arch="${_cputype}-${_ostype}"

    RETVAL="$_arch"
}

say() {
    printf '%s\n' "$1"
}

err() {
    say "$1" >&2
    exit 1
}

info() {
    if $_ansi_escapes_are_valid; then
        printf "\33[1minfo:\33[0m $1\n" 1>&2
    else
        printf '%s\n' "info: $1" 1>&2
    fi
}

need_cmd() {
    if ! check_cmd "$1"; then
        err "need '$1' (command not found)"
    fi
}

check_cmd() {
    command -v "$1" > /dev/null 2>&1
}

assert_nz() {
    if [ -z "$1" ]; then err "assert_nz $2"; fi
}

# Run a command that should never fail. If the command fails execution
# will immediately terminate with an error showing the failing
# command.
ensure() {
    if ! "$@"; then err "command failed: $*"; fi
}

# This is just for indicating that commands' results are being
# intentionally ignored. Usually, because it's being executed
# as part of error handling.
ignore() {
    "$@"
}

# This wraps curl or wget. Try curl first, if not installed,
# use wget instead.
downloader() {
    local _dld
    local _err
    local _status
    if check_cmd curl; then
        _dld=curl
    elif check_cmd wget; then
        _dld=wget
    else
        _dld='curl or wget' # to be used in error message of need_cmd
    fi

    if [ "$1" = --check ]; then
        need_cmd "$_dld"
    elif [ "$_dld" = curl ]; then
        _err=$(curl --silent --show-error --fail --location "$1" --output "$2" 2>&1)
        _status=$?
        if [ -n "$_err" ]; then
            echo "$_err" >&2
            if echo "$_err" | grep -q 404; then
                err "installer for platform '$3' not found, this may be unsupported"
            fi
        fi
        return $_status
    elif [ "$_dld" = wget ]; then
        _err=$(wget "$1" -q -O "$2" 2>&1)
        _status=$?
        if [ -n "$_err" ]; then
            echo "$_err" >&2
            if echo "$_err" | grep -q ' 404 Not Found'; then
                err "installer for platform '$3' not found, this may be unsupported"
            fi
        fi
        return $_status
    else
        err "Unknown downloader"   # should not reach here
    fi
}

fetcher() {
    local _dld
    local _res
    if check_cmd curl; then
        _dld=curl
    elif check_cmd wget; then
        _dld=wget
    else
        _dld='curl or wget' # to be used in error message of need_cmd
    fi

    if [ "$1" = --check ]; then
        need_cmd "$_dld"
    elif [ "$_dld" = curl ]; then
        _res=$(curl --silent --show-error --fail --location "$1")
        echo "$_res"
        return
    elif [ "$_dld" = wget ]; then
        _res="$(wget "$1" -q -O -)"
        echo "$_res"
        return
    else
        err "Unknown fetcher"   # should not reach here
    fi
}

main "$@" || exit 1
