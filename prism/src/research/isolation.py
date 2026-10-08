"""Legacy Linux seccomp isolation; fail closed if unavailable."""
import ctypes
import errno
def restrict_io():
    lib=ctypes.CDLL('libseccomp.so.2',use_errno=True)
    lib.seccomp_init.restype=ctypes.c_void_p
    lib.seccomp_init.argtypes=[ctypes.c_uint32]
    lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
    lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    lib.seccomp_load.argtypes=[ctypes.c_void_p]
    lib.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=lib.seccomp_init(0x7fff0000)
    if not ctx: raise RuntimeError('seccomp init failed')
    for name in ('open','openat','openat2','socket','socketpair','connect','execve','execveat',
                 'fork','vfork','clone','clone3','ptrace','process_vm_readv','process_vm_writev','io_uring_setup'):
        n=lib.seccomp_syscall_resolve_name(name.encode())
        if n>=0 and lib.seccomp_rule_add(ctx,0x00050000|errno.EPERM,n,0)!=0:
            raise RuntimeError('seccomp rule failed '+name)
    if lib.seccomp_load(ctx)!=0: raise RuntimeError('seccomp load failed')
    lib.seccomp_release(ctx)

