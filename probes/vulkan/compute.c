/* Bounded, headless compute/readback test. This does not test macOS or Metal. */
#include <vulkan/vulkan.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define COUNT 65536u
#define CHECK(call)                                                                                \
    do {                                                                                           \
        VkResult result_ = (call);                                                                 \
        if (result_ != VK_SUCCESS) {                                                               \
            fprintf(stderr, "FAIL: %s returned %d\n", #call, result_);                             \
            exit(1);                                                                               \
        }                                                                                          \
    } while (0)
#define REQUIRE(ok, message)                                                                       \
    do {                                                                                           \
        if (!(ok)) {                                                                               \
            fprintf(stderr, "FAIL: %s\n", message);                                                \
            exit(1);                                                                               \
        }                                                                                          \
    } while (0)

int main(int argc, char **argv) {
    REQUIRE(argc == 2, "usage: vulkan-compute shader.spv");
    setvbuf(stdout, NULL, _IONBF, 0);
    FILE *file = fopen(argv[1], "rb");
    REQUIRE(file != NULL, "open shader");
    REQUIRE(fseek(file, 0, SEEK_END) == 0, "seek shader");
    long length = ftell(file);
    REQUIRE(length > 0 && length <= 1048576 && length % 4 == 0, "shader size");
    rewind(file);
    uint32_t *code = malloc((size_t)length);
    REQUIRE(code != NULL, "shader allocation");
    REQUIRE(fread(code, 1, (size_t)length, file) == (size_t)length, "read shader");
    REQUIRE(fclose(file) == 0, "close shader");

    VkApplicationInfo app = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "hmacos-arm-host-probe",
        .apiVersion = VK_API_VERSION_1_2,
    };
    VkInstanceCreateInfo instance_info = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &app,
    };
    VkInstance instance;
    CHECK(vkCreateInstance(&instance_info, NULL, &instance));
    uint32_t count = 0;
    CHECK(vkEnumeratePhysicalDevices(instance, &count, NULL));
    REQUIRE(count > 0, "no Vulkan devices");
    VkPhysicalDevice *devices = calloc(count, sizeof(*devices));
    REQUIRE(devices != NULL, "device allocation");
    CHECK(vkEnumeratePhysicalDevices(instance, &count, devices));
    VkPhysicalDevice physical = VK_NULL_HANDLE;
    VkPhysicalDeviceProperties properties;
    for (uint32_t i = 0; i < count; i++) {
        vkGetPhysicalDeviceProperties(devices[i], &properties);
        printf("device=%s vendor=0x%x id=0x%x type=%u\n", properties.deviceName,
               properties.vendorID, properties.deviceID, properties.deviceType);
        if (properties.vendorID == 0x10de && properties.deviceID == 0x2e12 &&
            properties.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU &&
            strstr(properties.deviceName, "GB10") != NULL)
            physical = devices[i];
    }
    free(devices);
    REQUIRE(physical != VK_NULL_HANDLE, "physical NVIDIA GB10 required; no CPU fallback");
    vkGetPhysicalDeviceProperties(physical, &properties);
    printf("selected=%s Vulkan=%u.%u.%u timestamp_period_ns=%g\n", properties.deviceName,
           VK_VERSION_MAJOR(properties.apiVersion), VK_VERSION_MINOR(properties.apiVersion),
           VK_VERSION_PATCH(properties.apiVersion), properties.limits.timestampPeriod);

    uint32_t extension_count = 0;
    CHECK(vkEnumerateDeviceExtensionProperties(physical, NULL, &extension_count, NULL));
    VkExtensionProperties *extensions = calloc(extension_count, sizeof(*extensions));
    REQUIRE(extensions != NULL, "extension allocation");
    CHECK(vkEnumerateDeviceExtensionProperties(physical, NULL, &extension_count, extensions));
    const char *interesting[] = {
        "VK_EXT_external_memory_host",
        "VK_EXT_external_memory_dma_buf",
        "VK_KHR_external_memory_fd",
        "VK_KHR_timeline_semaphore",
    };
    for (size_t i = 0; i < sizeof(interesting) / sizeof(interesting[0]); i++) {
        int found = 0;
        for (uint32_t j = 0; j < extension_count; j++)
            found |= strcmp(interesting[i], extensions[j].extensionName) == 0;
        printf("%s=%d\n", interesting[i], found);
    }
    free(extensions);

    uint32_t family_count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &family_count, NULL);
    VkQueueFamilyProperties *families = calloc(family_count, sizeof(*families));
    REQUIRE(families != NULL, "queue allocation");
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &family_count, families);
    uint32_t family = UINT32_MAX;
    for (uint32_t i = 0; i < family_count; i++) {
        if (families[i].queueCount && (families[i].queueFlags & VK_QUEUE_COMPUTE_BIT) &&
            families[i].timestampValidBits == 64) {
            family = i;
            break;
        }
    }
    free(families);
    REQUIRE(family != UINT32_MAX, "compute queue with 64-bit timestamps required");
    float priority = 1.0f;
    VkDeviceQueueCreateInfo queue_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = family,
        .queueCount = 1,
        .pQueuePriorities = &priority,
    };
    VkDeviceCreateInfo device_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queue_info,
    };
#ifdef PROBE_HOST_IMPORT
    const char *import_extension = "VK_EXT_external_memory_host";
    device_info.enabledExtensionCount = 1;
    device_info.ppEnabledExtensionNames = &import_extension;
#endif
    VkDevice device;
    CHECK(vkCreateDevice(physical, &device_info, NULL, &device));
    VkQueue queue;
    vkGetDeviceQueue(device, family, 0, &queue);
    VkDeviceSize bytes = COUNT * sizeof(uint32_t);
    VkBufferCreateInfo buffer_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = bytes,
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
#ifdef PROBE_HOST_IMPORT
    VkExternalMemoryBufferCreateInfo external_buffer = {
        .sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
        .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT,
    };
    buffer_info.pNext = &external_buffer;
#endif
    VkBuffer buffer;
    CHECK(vkCreateBuffer(device, &buffer_info, NULL, &buffer));
    VkMemoryRequirements requirements;
    vkGetBufferMemoryRequirements(device, buffer, &requirements);
    VkPhysicalDeviceMemoryProperties memory_properties;
    vkGetPhysicalDeviceMemoryProperties(physical, &memory_properties);
#ifdef PROBE_HOST_IMPORT
    VkPhysicalDeviceExternalMemoryHostPropertiesEXT host_properties = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT,
    };
    VkPhysicalDeviceProperties2 properties2 = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,
        .pNext = &host_properties,
    };
    vkGetPhysicalDeviceProperties2(physical, &properties2);
    VkDeviceSize alignment = host_properties.minImportedHostPointerAlignment;
    if (alignment < 16384)
        alignment = 16384;
    REQUIRE(alignment <= 1048576 && (alignment & (alignment - 1)) == 0,
            "unexpected host import alignment");
    VkDeviceSize import_size = (requirements.size + alignment - 1) & ~(alignment - 1);
    void *host_pointer = aligned_alloc((size_t)alignment, (size_t)import_size);
    REQUIRE(host_pointer != NULL, "aligned host allocation");
    PFN_vkGetMemoryHostPointerPropertiesEXT get_host_properties =
        (PFN_vkGetMemoryHostPointerPropertiesEXT)vkGetDeviceProcAddr(
            device, "vkGetMemoryHostPointerPropertiesEXT");
    REQUIRE(get_host_properties != NULL, "host import entry point");
    VkMemoryHostPointerPropertiesEXT pointer_properties = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_HOST_POINTER_PROPERTIES_EXT,
    };
    CHECK(get_host_properties(device, VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT,
                              host_pointer, &pointer_properties));
    requirements.memoryTypeBits &= pointer_properties.memoryTypeBits;
    printf("host import: driver_min_alignment=%" PRIu64 " actual_alignment=%" PRIu64
           " allocation_bytes=%" PRIu64 "\n",
           (uint64_t)host_properties.minImportedHostPointerAlignment, (uint64_t)alignment,
           (uint64_t)import_size);
#endif
    uint32_t memory_type = UINT32_MAX;
    VkMemoryPropertyFlags flags =
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
    for (uint32_t i = 0; i < memory_properties.memoryTypeCount; i++)
        if ((requirements.memoryTypeBits & (1u << i)) &&
            (memory_properties.memoryTypes[i].propertyFlags & flags) == flags) {
            memory_type = i;
            break;
        }
    REQUIRE(memory_type != UINT32_MAX, "host-coherent memory required");
    VkMemoryAllocateInfo allocation = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size,
        .memoryTypeIndex = memory_type,
    };
#ifdef PROBE_HOST_IMPORT
    VkImportMemoryHostPointerInfoEXT import_info = {
        .sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_HOST_POINTER_INFO_EXT,
        .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT,
        .pHostPointer = host_pointer,
    };
    allocation.pNext = &import_info;
    allocation.allocationSize = import_size;
#endif
    VkDeviceMemory memory;
    CHECK(vkAllocateMemory(device, &allocation, NULL, &memory));
    CHECK(vkBindBufferMemory(device, buffer, memory, 0));
    uint32_t *values;
#ifdef PROBE_HOST_IMPORT
    values = host_pointer;
#else
    CHECK(vkMapMemory(device, memory, 0, bytes, 0, (void **)&values));
#endif
    for (uint32_t i = 0; i < COUNT; i++)
        values[i] = i ^ 0xa5a5a5a5u;

    VkDescriptorSetLayoutBinding binding = {
        .binding = 0,
        .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
        .descriptorCount = 1,
        .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT,
    };
    VkDescriptorSetLayoutCreateInfo layout_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount = 1,
        .pBindings = &binding,
    };
    VkDescriptorSetLayout layout;
    CHECK(vkCreateDescriptorSetLayout(device, &layout_info, NULL, &layout));
    VkDescriptorPoolSize pool_size = {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1};
    VkDescriptorPoolCreateInfo pool_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets = 1,
        .poolSizeCount = 1,
        .pPoolSizes = &pool_size,
    };
    VkDescriptorPool pool;
    CHECK(vkCreateDescriptorPool(device, &pool_info, NULL, &pool));
    VkDescriptorSetAllocateInfo set_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
        .descriptorPool = pool,
        .descriptorSetCount = 1,
        .pSetLayouts = &layout,
    };
    VkDescriptorSet set;
    CHECK(vkAllocateDescriptorSets(device, &set_info, &set));
    VkDescriptorBufferInfo descriptor_buffer = {buffer, 0, bytes};
    VkWriteDescriptorSet write = {
        .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
        .dstSet = set,
        .dstBinding = 0,
        .descriptorCount = 1,
        .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
        .pBufferInfo = &descriptor_buffer,
    };
    vkUpdateDescriptorSets(device, 1, &write, 0, NULL);
    VkPipelineLayoutCreateInfo pipeline_layout_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1,
        .pSetLayouts = &layout,
    };
    VkPipelineLayout pipeline_layout;
    CHECK(vkCreatePipelineLayout(device, &pipeline_layout_info, NULL, &pipeline_layout));
    VkShaderModuleCreateInfo shader_info = {
        .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = (size_t)length,
        .pCode = code,
    };
    VkShaderModule shader;
    CHECK(vkCreateShaderModule(device, &shader_info, NULL, &shader));
    free(code);
    VkComputePipelineCreateInfo pipeline_info = {
        .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                  .stage = VK_SHADER_STAGE_COMPUTE_BIT,
                  .module = shader,
                  .pName = "main"},
        .layout = pipeline_layout,
    };
    VkPipeline pipeline;
    CHECK(vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &pipeline_info, NULL, &pipeline));
    VkCommandPoolCreateInfo command_pool_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .queueFamilyIndex = family,
    };
    VkCommandPool command_pool;
    CHECK(vkCreateCommandPool(device, &command_pool_info, NULL, &command_pool));
    VkCommandBufferAllocateInfo command_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = command_pool,
        .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
        .commandBufferCount = 1,
    };
    VkCommandBuffer command;
    CHECK(vkAllocateCommandBuffers(device, &command_info, &command));
    VkQueryPoolCreateInfo query_info = {
        .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
        .queryType = VK_QUERY_TYPE_TIMESTAMP,
        .queryCount = 2,
    };
    VkQueryPool queries;
    CHECK(vkCreateQueryPool(device, &query_info, NULL, &queries));
    VkCommandBufferBeginInfo begin = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    CHECK(vkBeginCommandBuffer(command, &begin));
    vkCmdResetQueryPool(command, queries, 0, 2);
    vkCmdWriteTimestamp(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, queries, 0);
    vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
    vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline_layout, 0, 1, &set, 0,
                            NULL);
    vkCmdDispatch(command, COUNT / 64, 1, 1);
    VkMemoryBarrier barrier = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT,
        .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
    };
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                         0, 1, &barrier, 0, NULL, 0, NULL);
    vkCmdWriteTimestamp(command, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, queries, 1);
    CHECK(vkEndCommandBuffer(command));
    VkFenceCreateInfo fence_info = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    VkFence fence;
    CHECK(vkCreateFence(device, &fence_info, NULL, &fence));
    VkSubmitInfo submit = {
        .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
        .commandBufferCount = 1,
        .pCommandBuffers = &command,
    };
    CHECK(vkQueueSubmit(queue, 1, &submit, fence));
    CHECK(vkWaitForFences(device, 1, &fence, VK_TRUE, UINT64_C(5000000000)));
    uint64_t timestamps[2];
    CHECK(vkGetQueryPoolResults(device, queries, 0, 2, sizeof(timestamps), timestamps,
                                sizeof(uint64_t), VK_QUERY_RESULT_64_BIT));
    REQUIRE(timestamps[1] > timestamps[0], "non-increasing GPU timestamps");
    printf("GPU timestamp delta_ns=%.0f\n",
           (timestamps[1] - timestamps[0]) * (double)properties.limits.timestampPeriod);
    for (uint32_t i = 0; i < COUNT; i++) {
        uint32_t expected = ((i ^ 0xa5a5a5a5u) * 1664525u + 1013904223u) ^ i;
        if (values[i] != expected) {
            fprintf(stderr, "FAIL: index=%u expected=0x%08x actual=0x%08x\n", i, expected,
                    values[i]);
            return 1;
        }
    }
    printf("PASS: physical GB10 compute, %u verified uint32 results, %" PRIu64 " bytes\n", COUNT,
           (uint64_t)bytes);
#ifdef PROBE_HOST_IMPORT
    puts("PASS: GPU read/write of imported 16 KiB-aligned host allocation");
#else
    vkUnmapMemory(device, memory);
#endif
    vkDestroyFence(device, fence, NULL);
    vkDestroyQueryPool(device, queries, NULL);
    vkDestroyCommandPool(device, command_pool, NULL);
    vkDestroyPipeline(device, pipeline, NULL);
    vkDestroyShaderModule(device, shader, NULL);
    vkDestroyPipelineLayout(device, pipeline_layout, NULL);
    vkDestroyDescriptorPool(device, pool, NULL);
    vkDestroyDescriptorSetLayout(device, layout, NULL);
    vkDestroyBuffer(device, buffer, NULL);
    vkFreeMemory(device, memory, NULL);
#ifdef PROBE_HOST_IMPORT
    free(host_pointer);
#endif
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    return 0;
}
