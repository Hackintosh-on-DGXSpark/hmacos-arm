"""Guarded, in-place CPU timer metadata update for the Apple flattened tree."""

import struct


def patch_timebase(tree, frequency):
    """Validate every CPU timebase before changing any bytes; return the count."""
    if not 0 < frequency <= 0xFFFFFFFF:
        raise ValueError("Invalid timer frequency")
    changes = []

    def visit(offset, depth, parent_is_cpus):
        if depth > 128 or offset + 8 > len(tree):
            raise ValueError("Truncated or excessively deep device tree")
        properties, children = struct.unpack_from("<II", tree, offset)
        cursor = offset + 8
        values = {}
        for _ in range(properties):
            if cursor + 36 > len(tree):
                raise ValueError("Truncated property header")
            name = bytes(tree[cursor : cursor + 32]).split(b"\0", 1)[0].decode("ascii")
            length = struct.unpack_from("<I", tree, cursor + 32)[0] & 0x00FFFFFF
            start = cursor + 36
            cursor = start + ((length + 3) & ~3)
            if cursor > len(tree) or name in values:
                raise ValueError("Truncated or duplicate device-tree property")
            values[name] = (start, length)
        if parent_is_cpus and "timebase-frequency" in values:
            start, length = values["timebase-frequency"]
            if (
                length not in (4, 8)
                or int.from_bytes(tree[start : start + length], "little") != 24000000
            ):
                raise ValueError("Unexpected CPU timebase metadata")
            changes.append((start, length))
        node_name = b""
        if "name" in values:
            start, length = values["name"]
            node_name = bytes(tree[start : start + length]).rstrip(b"\0")
        is_cpus = depth == 1 and node_name == b"cpus"
        for _ in range(children):
            cursor = visit(cursor, depth + 1, is_cpus)
        return cursor

    visit(0, 0, False)
    if not changes:
        raise ValueError("No CPU timebase properties found")
    for start, length in changes:
        tree[start : start + length] = frequency.to_bytes(length, "little")
    return len(changes)
