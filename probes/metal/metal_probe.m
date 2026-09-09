/* Guest-only Metal correctness probe. Correlate results with the host GPU log. */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dispatch/dispatch.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/sysctl.h>
#include <unistd.h>

#define COUNT 65536u
#define REQUIRE(condition, message)                                                                \
    do {                                                                                           \
        if (!(condition)) {                                                                        \
            fprintf(stderr, "FAIL: %s\n", message);                                                \
            return 1;                                                                              \
        }                                                                                          \
    } while (0)

int main(int argc, const char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    alarm(30);
    BOOL negative = NO, explicitDevice = NO;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--negative-control") == 0)
            negative = YES;
        else if (strcmp(argv[i], "--explicit-device") == 0)
            explicitDevice = YES;
        else
            REQUIRE(NO, "usage: metal-probe [--explicit-device] [--negative-control]");
    }
    char model[128] = {0};
    size_t modelSize = sizeof(model);
    REQUIRE(sysctlbyname("hw.model", model, &modelSize, NULL, 0) == 0,
            "cannot identify guest model");
    REQUIRE(strncmp(model, "VirtualMac", 10) == 0,
            "run inside the disposable VirtualMac guest, not the host Mac");
    @autoreleasepool {
        printf("model=%s uid=%u os=%s\n", model, getuid(),
               NSProcessInfo.processInfo.operatingSystemVersionString.UTF8String);
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
        printf("default_device=%s enumerated_devices=%lu\n",
               device ? device.name.UTF8String : "none", (unsigned long)devices.count);
        for (id<MTLDevice> candidate in devices)
            printf("enumerated_device=%s registry_id=0x%llx\n", candidate.name.UTF8String,
                   (unsigned long long)candidate.registryID);
        if (explicitDevice) {
            REQUIRE(devices.count == 1, "explicit selection requires exactly one Metal device");
            device = devices[0];
            REQUIRE([device.name isEqualToString:@"Apple Paravirtual device"],
                    "explicit selection requires the Apple paravirtual device");
            puts("selection=explicit-paravirtual-device");
        }
        REQUIRE(device != nil, "no Metal device");
        printf("model=%s device=%s registry_id=0x%llx unified=%d\n", model, device.name.UTF8String,
               (unsigned long long)device.registryID, device.hasUnifiedMemory);
        printf("os=%s mode=%s count=%u\n",
               NSProcessInfo.processInfo.operatingSystemVersionString.UTF8String,
               negative ? "negative-control" : "correctness", COUNT);
        NSString *source = @"#include <metal_stdlib>\n"
                            "using namespace metal;\n"
                            "kernel void probe(device const uint *src [[buffer(0)]], "
                            "device uint *dst [[buffer(1)]], uint i [[thread_position_in_grid]]) { "
                            "dst[i] = (src[i] * 1664525u + 1013904223u) ^ (i >> 3); }\n";
        NSError *error = nil;
        id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
        if (!library) {
            fprintf(stderr, "FAIL: Metal compilation: %s\n", error.description.UTF8String);
            return 1;
        }
        id<MTLFunction> function = [library newFunctionWithName:@"probe"];
        REQUIRE(function != nil, "compiled Metal function missing");
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:function
                                                                                     error:&error];
        if (!pipeline) {
            fprintf(stderr, "FAIL: Metal pipeline: %s\n", error.description.UTF8String);
            return 1;
        }
        REQUIRE(pipeline.maxTotalThreadsPerThreadgroup >= 128, "128 threads required");
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLBuffer> input = [device newBufferWithLength:COUNT * sizeof(uint32_t)
                                                  options:MTLResourceStorageModeShared];
        id<MTLBuffer> output = [device newBufferWithLength:COUNT * sizeof(uint32_t)
                                                   options:MTLResourceStorageModeShared];
        REQUIRE(queue && input && output, "queue/buffer allocation failed");
        uint32_t *in = input.contents, *out = output.contents;
        REQUIRE(in && out, "shared buffer mapping failed");
        const uint32_t seeds[] = {0xa5a5a5a5u, 0x13579bdfu};
        for (unsigned round = 0; round < 2; round++) {
            for (uint32_t i = 0; i < COUNT; i++) {
                in[i] = i ^ seeds[round];
                out[i] = 0xdeadbeefu;
            }
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            REQUIRE(command && encoder, "command/encoder allocation failed");
            [encoder setComputePipelineState:pipeline];
            [encoder setBuffer:input offset:0 atIndex:0];
            [encoder setBuffer:output offset:0 atIndex:1];
            [encoder dispatchThreadgroups:MTLSizeMake(COUNT / 128, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
            [encoder endEncoding];
            dispatch_semaphore_t done = dispatch_semaphore_create(0);
            [command addCompletedHandler:^(id<MTLCommandBuffer> finished) {
              (void)finished;
              dispatch_semaphore_signal(done);
            }];
            [command commit];
            REQUIRE(dispatch_semaphore_wait(
                        done, dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC)) == 0,
                    "Metal command timed out");
            if (command.status != MTLCommandBufferStatusCompleted) {
                fprintf(stderr, "FAIL: Metal command status=%lu error=%s\n",
                        (unsigned long)command.status, command.error.description.UTF8String);
                return 1;
            }
            unsigned mismatches = 0;
            uint64_t checksum = 0;
            for (uint32_t i = 0; i < COUNT; i++) {
                uint32_t expected = ((i ^ seeds[round]) * 1664525u + 1013904223u) ^ (i >> 3);
                if (negative && i == COUNT / 2)
                    expected ^= 1u;
                if (out[i] != expected) {
                    if (mismatches == 0)
                        fprintf(stderr, "first_mismatch index=%u expected=%08x actual=%08x\n", i,
                                expected, out[i]);
                    mismatches++;
                }
                checksum += out[i];
            }
            printf("round=%u seed=%08x checksum=%016llx mismatches=%u\n", round, seeds[round],
                   (unsigned long long)checksum, mismatches);
            REQUIRE(mismatches == 0, "GPU result differs from CPU oracle");
        }
        puts("PASS: guest Metal compute/readback; 2 x 65536 uint32 results verified");
    }
    return 0;
}
