/* Standalone Linux arm64 KVM execution diagnostic, not a VM implementation. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/kvm.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#if !defined(__linux__) || !defined(__aarch64__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "This experiment requires little-endian Linux arm64"
#endif

#define RAM_BYTES (2UL * 1024 * 1024)
#define GUEST_BASE UINT64_C(0x40000000)
#define MMIO_BASE UINT64_C(0x10000000)
#define PAC_POINTER UINT64_C(0x40000100)
#ifndef TEST_EXPECTED_VALUE
#define TEST_EXPECTED_VALUE UINT64_C(0x4b564d5000061df0)
#endif

#define CORE_REG(name)                                                                             \
    (KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM_CORE | KVM_REG_ARM_CORE_REG(regs.name))
#define IOCTL(fd, op, arg) checked_ioctl(fd, op, (unsigned long)(arg), #op)
#define CAP(fd, cap) check_cap(fd, cap, #cap)

/* No host-computed result is injected into this position-independent payload. */
extern const unsigned char kvm_probe_guest_start[], kvm_probe_guest_end[];
__asm__(".pushsection .rodata.kvm_probe_guest,\"a\",%progbits\n"
        ".balign 4\n"
        ".global kvm_probe_guest_start, kvm_probe_guest_end\n"
        "kvm_probe_guest_start:\n"
#ifdef PROBE_VMAPPLE_HVC
        "movz x0, #0xc100, lsl #16\n"
        "mov x1, #0x123\n"
        "hvc #0\n"
        "mov x11, x0\n"
        "mrs x12, cntfrq_el0\n"
#endif
        "mov x0, #0x1234\n"
        "mov x1, #0x56\n"
        "mul x2, x0, x1\n"
        "add x2, x2, #0x78\n"
        "movz x3, #0x4d50, lsl #32\n"
        "movk x3, #0x4b56, lsl #48\n"
        "eor x2, x2, x3\n"
        "mov x4, #0x10000000\n"
        "cbz x10, 1f\n"
        "mov x5, #0x40000000\n"
        "add x5, x5, #0x100\n"
        "mov x6, #0x5678\n"
        ".inst 0xdac100c5\n" /* pacia x5, x6 (not a HINT-space NOP) */
        "mov x7, x5\n"
        ".inst 0xdac110c5\n" /* autia x5, x6 */
        "1: str x2, [x4]\n"
        "2: b 2b\n"
        "kvm_probe_guest_end:\n"
        ".popsection\n");

static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(EXIT_FAILURE); /* No forks: process exit also releases KVM/mmap. */
    }
}

static void system_error(const char *operation) {
    fprintf(stderr, "FAIL: %s: %s\n", operation, strerror(errno));
    exit(EXIT_FAILURE);
}

static int checked_ioctl(int fd, unsigned long request, unsigned long argument, const char *name) {
    for (unsigned int retries = 0;; ++retries) {
        int result = ioctl(fd, request, argument);
        if (result >= 0)
            return result;
        if (errno != EINTR || retries == 8)
            system_error(name);
    }
}

static int check_cap(int kvm, int capability, const char *name) {
    int value = IOCTL(kvm, KVM_CHECK_EXTENSION, capability);
    printf("%s=%d\n", name, value);
    return value;
}

static uint64_t get_reg(int vcpu, uint64_t id) {
    uint64_t value = 0;
    struct kvm_one_reg reg = {.id = id, .addr = (uintptr_t)&value};
    IOCTL(vcpu, KVM_GET_ONE_REG, &reg);
    return value;
}

static void set_reg(int vcpu, uint64_t id, uint64_t value) {
    struct kvm_one_reg reg = {.id = id, .addr = (uintptr_t)&value};
    IOCTL(vcpu, KVM_SET_ONE_REG, &reg);
}

int main(void) {
    require(setvbuf(stdout, NULL, _IONBF, 0) == 0, "setvbuf");
    if (signal(SIGALRM, SIG_DFL) == SIG_ERR)
        system_error("signal(SIGALRM)");
    alarm(8);
    require(getuid() != 0 && geteuid() != 0, "run as a nonroot user");
    long page_size = sysconf(_SC_PAGESIZE);
    require(page_size > 0 && RAM_BYTES % (unsigned long)page_size == 0,
            "invalid host page size for RAM slot");
    printf("uid=%lu euid=%lu gid=%lu host_page_size=%ld\n", (unsigned long)getuid(),
           (unsigned long)geteuid(), (unsigned long)getgid(), page_size);
    printf("limits: vcpus=1 ram_bytes=%lu alarm_seconds=8 ioctl_eintr_retries=8\n", RAM_BYTES);
    printf("TEST_EXPECTED_VALUE=0x%016" PRIx64 "\n", (uint64_t)TEST_EXPECTED_VALUE);

    int kvm = open("/dev/kvm", O_RDWR | O_CLOEXEC);
    if (kvm < 0)
        system_error("open(/dev/kvm)");
    int api = IOCTL(kvm, KVM_GET_API_VERSION, 0);
    printf("KVM_API_VERSION=%d\n", api);
    require(api == KVM_API_VERSION, "unexpected KVM API version");
    require(CAP(kvm, KVM_CAP_ONE_REG) > 0, "KVM_CAP_ONE_REG is required");
    CAP(kvm, KVM_CAP_ARM_VM_IPA_SIZE);
    int pac_address = CAP(kvm, KVM_CAP_ARM_PTRAUTH_ADDRESS);
    int pac_generic = CAP(kvm, KVM_CAP_ARM_PTRAUTH_GENERIC);
    int pauth = pac_address > 0 && pac_generic > 0;
    CAP(kvm, KVM_CAP_ARM_PSCI);
    int psci = CAP(kvm, KVM_CAP_ARM_PSCI_0_2);
    int user_irq = CAP(kvm, KVM_CAP_ARM_USER_IRQ);
    CAP(kvm, KVM_CAP_COUNTER_OFFSET);

    int vm = IOCTL(kvm, KVM_CREATE_VM, 0); /* Default 40-bit IPA limit. */
#ifdef PROBE_VMAPPLE_HVC
    struct kvm_smccc_filter filter = {
        .base = 0xc1000000,
        .nr_functions = 0x100,
        .action = KVM_SMCCC_FILTER_FWD_TO_USER,
    };
    struct kvm_device_attr attr = {
        .group = KVM_ARM_VM_SMCCC_CTRL,
        .attr = KVM_ARM_VM_SMCCC_FILTER,
        .addr = (uintptr_t)&filter,
    };
    IOCTL(vm, KVM_SET_DEVICE_ATTR, &attr);
    puts("VMApple HVC filter 0xc1000000..0xc10000ff installed");
#endif
    int vcpu = IOCTL(vm, KVM_CREATE_VCPU, 0);
    struct kvm_vcpu_init init = {0};
    IOCTL(vm, KVM_ARM_PREFERRED_TARGET, &init);
    memset(init.features, 0, sizeof(init.features));
    if (psci > 0)
        init.features[0] |= 1U << KVM_ARM_VCPU_PSCI_0_2;
    if (pauth)
        init.features[0] |=
            (1U << KVM_ARM_VCPU_PTRAUTH_ADDRESS) | (1U << KVM_ARM_VCPU_PTRAUTH_GENERIC);
    IOCTL(vcpu, KVM_ARM_VCPU_INIT, &init);
    printf("KVM_CREATE_VM=OK KVM_CREATE_VCPU=OK target=%u features[0]=0x%x pauth=%s\n", init.target,
           init.features[0], pauth ? "enabled" : "unavailable");

    uint64_t isar1 = get_reg(vcpu, ARM64_SYS_REG(3, 0, 0, 6, 1));
    uint64_t isar2 = get_reg(vcpu, ARM64_SYS_REG(3, 0, 0, 6, 2));
    uint64_t mmfr0 = get_reg(vcpu, ARM64_SYS_REG(3, 0, 0, 7, 0));
    printf("guest ID_AA64ISAR1_EL1=0x%016" PRIx64 "\n", isar1);
    printf("guest ID_AA64ISAR2_EL1=0x%016" PRIx64 "\n", isar2);
    printf("guest ID_AA64MMFR0_EL1=0x%016" PRIx64 "\n", mmfr0);
    printf("raw PAuth fields: APA=0x%" PRIx64 " API=0x%" PRIx64 " GPA=0x%" PRIx64 " GPI=0x%" PRIx64
           " APA3=0x%" PRIx64 " GPA3=0x%" PRIx64 "\n",
           (isar1 >> 4) & 15, (isar1 >> 8) & 15, (isar1 >> 24) & 15, (isar1 >> 28) & 15,
           (isar2 >> 12) & 15, (isar2 >> 8) & 15);
    unsigned int tgran16 = (unsigned int)((mmfr0 >> 20) & 15);
    const char *granule = tgran16 == 0   ? "not supported"
                          : tgran16 == 1 ? "supported"
                          : tgran16 == 2 ? "supported, including 52-bit addresses"
                                         : "reserved/unknown encoding";
    printf("raw TGran16[23:20]=0x%x (%s); raw PARange[3:0]=0x%" PRIx64 "\n", tgran16, granule,
           mmfr0 & 15);
    if (psci > 0) {
        uint64_t version = get_reg(vcpu, KVM_REG_ARM_PSCI_VERSION);
        printf("guest PSCI_VERSION=0x%08" PRIx64 " (%" PRIu64 ".%" PRIu64 ")\n", version,
               version >> 16, version & 0xffff);
#ifdef PROBE_VMAPPLE_HVC
        set_reg(vcpu, KVM_REG_ARM_PSCI_VERSION, 0x00010001);
        require(get_reg(vcpu, KVM_REG_ARM_PSCI_VERSION) == 0x00010001,
                "PSCI 1.1 configuration failed");
        puts("PASS: guest PSCI configured to Ventura-compatible version 1.1");
#endif
    }
    if (user_irq > 0) {
        set_reg(vcpu, KVM_REG_ARM_TIMER_CTL, 0);
        set_reg(vcpu, KVM_REG_ARM_PTIMER_CTL, 0);
        printf("guest timer controls (disabled): virtual=0x%" PRIx64 " physical=0x%" PRIx64 "\n",
               get_reg(vcpu, KVM_REG_ARM_TIMER_CTL), get_reg(vcpu, KVM_REG_ARM_PTIMER_CTL));
    }

    void *ram = mmap(NULL, RAM_BYTES, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (ram == MAP_FAILED)
        system_error("mmap(guest RAM)");
    size_t guest_bytes = (uintptr_t)kvm_probe_guest_end - (uintptr_t)kvm_probe_guest_start;
    require(guest_bytes > 0 && guest_bytes <= RAM_BYTES, "invalid guest payload size");
    memcpy(ram, kvm_probe_guest_start, guest_bytes);
    __builtin___clear_cache((char *)ram, (char *)ram + guest_bytes);
    struct kvm_userspace_memory_region memory = {
        .slot = 0,
        .guest_phys_addr = GUEST_BASE,
        .memory_size = RAM_BYTES,
        .userspace_addr = (uintptr_t)ram,
    };
    IOCTL(vm, KVM_SET_USER_MEMORY_REGION, &memory);
    int run_bytes = IOCTL(kvm, KVM_GET_VCPU_MMAP_SIZE, 0);
    require((size_t)run_bytes >= sizeof(struct kvm_run), "short kvm_run mapping");
    struct kvm_run *run =
        mmap(NULL, (size_t)run_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, vcpu, 0);
    if (run == MAP_FAILED)
        system_error("mmap(kvm_run)");
    printf("RAM slot=0 gpa=0x%08" PRIx64 " size=%lu guest_code_bytes=%zu\n", GUEST_BASE, RAM_BYTES,
           guest_bytes);

    set_reg(vcpu, CORE_REG(pc), GUEST_BASE);
    set_reg(vcpu, CORE_REG(pstate), 0x3c5); /* EL1h, DAIF masked. */
    set_reg(vcpu, CORE_REG(regs[10]), (uint64_t)pauth);
    uint64_t sctlr = get_reg(vcpu, ARM64_SYS_REG(3, 0, 1, 0, 0));
    sctlr &= ~((UINT64_C(1) << 25) | 1); /* Little endian, stage-1 MMU off. */
    if (pauth) {
        sctlr |= UINT64_C(1) << 31; /* SCTLR_EL1.EnIA */
        set_reg(vcpu, ARM64_SYS_REG(3, 0, 2, 0, 2), 16 | (16UL << 16));
        /* Public synthetic APIA key, not a VM identity or credential. */
        set_reg(vcpu, ARM64_SYS_REG(3, 0, 2, 1, 0), UINT64_C(0x0123456789abcdef));
        set_reg(vcpu, ARM64_SYS_REG(3, 0, 2, 1, 1), UINT64_C(0xfedcba9876543210));
    }
#ifdef PROBE_16K
    require(tgran16 == 1 || tgran16 == 2, "16 KiB guest granule unavailable");
    /* 48-bit VA: 16 KiB L0/L1/L2 tables with identity-mapped 32 MiB blocks. */
    uint64_t *l0 = (uint64_t *)((char *)ram + 0x4000);
    uint64_t *l1 = (uint64_t *)((char *)ram + 0x8000);
    uint64_t *l2 = (uint64_t *)((char *)ram + 0xc000);
    l0[0] = (GUEST_BASE + 0x8000) | 3;
    l1[0] = (GUEST_BASE + 0xc000) | 3;
    l2[GUEST_BASE >> 25] = GUEST_BASE | 1 | (1 << 10) | (3 << 8);
    l2[MMIO_BASE >> 25] =
        MMIO_BASE | 1 | (1 << 10) | (1 << 2) | (UINT64_C(1) << 53) | (UINT64_C(1) << 54);
    set_reg(vcpu, ARM64_SYS_REG(3, 0, 10, 2, 0), 0xff); /* MAIR: normal/device. */
    set_reg(vcpu, ARM64_SYS_REG(3, 0, 2, 0, 0), GUEST_BASE + 0x4000);
    uint64_t tcr = 16 | (1 << 8) | (1 << 10) | (3 << 12) | (2 << 14) | (16 << 16) | (1 << 23) |
                   (1UL << 30) | (2UL << 32);
    set_reg(vcpu, ARM64_SYS_REG(3, 0, 2, 0, 2), tcr);
    sctlr |= 1;
    printf("16 KiB guest page tables enabled: TTBR0=0x%08" PRIx64 " TCR=0x%016" PRIx64 "\n",
           GUEST_BASE + 0x4000, tcr);
#endif
    set_reg(vcpu, ARM64_SYS_REG(3, 0, 1, 0, 0), sctlr);
    printf("guest SCTLR_EL1=0x%016" PRIx64 " (MMU %s)\n", sctlr, (sctlr & 1) ? "on" : "off");

    IOCTL(vcpu, KVM_RUN, 0);
#ifdef PROBE_VMAPPLE_HVC
    printf("HVC exit_reason=%u nr=0x%" PRIx64 "\n", run->exit_reason, (uint64_t)run->hypercall.nr);
    require(run->exit_reason == KVM_EXIT_HYPERCALL && run->hypercall.nr == 0xc1000000,
            "Apple-range HVC was not forwarded");
    require(get_reg(vcpu, CORE_REG(regs[1])) == 0x123, "HVC argument changed");
    /* Synthetic response tests transport only, not Apple's PAC service. */
    set_reg(vcpu, CORE_REG(regs[0]), 0x42);
    run->hypercall.ret = 0x42;
    IOCTL(vcpu, KVM_RUN, 0);
    require(get_reg(vcpu, CORE_REG(regs[11])) == 0x42, "HVC response not recovered");
    printf("PASS: Apple-range HVC forward/resume; CNTFRQ_EL0=%" PRIu64 " Hz\n",
           get_reg(vcpu, CORE_REG(regs[12])));
    uint64_t apple_apctl = 0;
    struct kvm_one_reg apple_reg = {
        .id = ARM64_SYS_REG(3, 6, 15, 15, 0),
        .addr = (uintptr_t)&apple_apctl,
    };
    int apple_result = ioctl(vcpu, KVM_GET_ONE_REG, &apple_reg);
    printf("Apple-specific APCTL_EL12 query: result=%d errno=%d (%s)\n", apple_result,
           apple_result < 0 ? errno : 0, apple_result < 0 ? strerror(errno) : "available");
#endif
    printf("KVM_RUN exit_reason=%u (expected KVM_EXIT_MMIO=%u)\n", run->exit_reason, KVM_EXIT_MMIO);
    require(run->exit_reason == KVM_EXIT_MMIO, "unexpected KVM exit reason");
    require(run->mmio.phys_addr == MMIO_BASE, "wrong MMIO address");
    require(run->mmio.len == sizeof(uint64_t), "wrong MMIO size");
    require(run->mmio.is_write == 1, "expected an MMIO write");
    uint64_t value;
    memcpy(&value, run->mmio.data, sizeof(value));
    printf("MMIO address=0x%08" PRIx64 " size=%u write=%u value=0x%016" PRIx64 "\n",
           (uint64_t)run->mmio.phys_addr, run->mmio.len, run->mmio.is_write, value);
    uint64_t x0 = get_reg(vcpu, CORE_REG(regs[0]));
    uint64_t x1 = get_reg(vcpu, CORE_REG(regs[1]));
    uint64_t x2 = get_reg(vcpu, CORE_REG(regs[2]));
    uint64_t x4 = get_reg(vcpu, CORE_REG(regs[4]));
    printf("guest x0=0x%016" PRIx64 " x1=0x%016" PRIx64 " x2=0x%016" PRIx64 " x4=0x%016" PRIx64
           "\n",
           x0, x1, x2, x4);
    require(value == (uint64_t)TEST_EXPECTED_VALUE,
            "MMIO write value differs from TEST_EXPECTED_VALUE");
    require(x0 == 0x1234 && x1 == 0x56 && x4 == MMIO_BASE,
            "guest operand/address registers differ");
    require(x2 == (uint64_t)TEST_EXPECTED_VALUE,
            "guest x2 arithmetic differs from TEST_EXPECTED_VALUE");
    puts("PASS: arithmetic registers and MMIO address/size/direction/value");
    if (pauth) {
        uint64_t authenticated = get_reg(vcpu, CORE_REG(regs[5]));
        uint64_t signed_pointer = get_reg(vcpu, CORE_REG(regs[7]));
        printf("PAuth original=0x%016" PRIx64 " signed=0x%016" PRIx64 " authenticated=0x%016" PRIx64
               "\n",
               PAC_POINTER, signed_pointer, authenticated);
        require(signed_pointer != PAC_POINTER &&
                    (signed_pointer & UINT64_C(0x0000ffffffffffff)) == PAC_POINTER,
                "PACIA did not produce a nonidentity signed pointer");
        require(authenticated == PAC_POINTER, "AUTIA did not recover the pointer");
        puts("PASS: PACIA changed the pointer and AUTIA recovered it");
    } else {
        puts("SKIP: PACIA/AUTIA (both PAuth capabilities are required)");
    }

    /* Do not resume the pending MMIO store; destroy this diagnostic VM. */
    if (munmap(run, (size_t)run_bytes) != 0)
        system_error("munmap(kvm_run)");
    if (close(vcpu) != 0)
        system_error("close(vcpu)");
    if (close(vm) != 0)
        system_error("close(vm)");
    if (munmap(ram, RAM_BYTES) != 0)
        system_error("munmap(guest RAM)");
    if (close(kvm) != 0)
        system_error("close(kvm)");
    alarm(0);
    puts("PASS: KVM execution probe");
    return EXIT_SUCCESS;
}
