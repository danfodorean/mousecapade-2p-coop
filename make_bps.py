"""Create a BPS patch (source-validating) from base -> modified."""
import zlib, sys

def num(n):                      # BPS variable-length number
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x); break
        out.append(x); n -= 1
    return bytes(out)

def create(src, dst, metadata=b''):
    p = bytearray(b'BPS1')
    p += num(len(src)) + num(len(dst)) + num(len(metadata)) + metadata
    i = 0
    while i < len(dst):
        same = i < len(src) and src[i] == dst[i]
        j = i
        while j < len(dst) and ((j < len(src) and src[j] == dst[j]) == same):
            j += 1
        run = j - i
        if same:
            p += num(((run - 1) << 2) | 0)          # SourceRead
        else:
            p += num(((run - 1) << 2) | 1) + dst[i:j]   # TargetRead
        i = j
    p += zlib.crc32(src).to_bytes(4, 'little')
    p += zlib.crc32(dst).to_bytes(4, 'little')
    p += zlib.crc32(bytes(p)).to_bytes(4, 'little')
    return bytes(p)

def apply(patch, src):
    """Reference applier used to verify what we just produced."""
    if patch[:4] != b'BPS1': raise ValueError("not BPS")
    pos = 4
    def rdnum():
        nonlocal pos
        data, shift = 0, 1
        while True:
            x = patch[pos]; pos += 1
            data += (x & 0x7F) * shift
            if x & 0x80: return data
            shift <<= 7; data += shift
    ssize, dsize, msize = rdnum(), rdnum(), rdnum()
    pos += msize
    if ssize != len(src): raise ValueError("source size mismatch")
    if zlib.crc32(src) != int.from_bytes(patch[-12:-8], 'little'):
        raise ValueError("source ROM checksum mismatch - wrong ROM")
    out = bytearray(); so = to = 0
    end = len(patch) - 12
    while pos < end:
        d = rdnum(); mode, ln = d & 3, (d >> 2) + 1
        if mode == 0:
            out += src[len(out):len(out)+ln]
        elif mode == 1:
            out += patch[pos:pos+ln]; pos += ln
        elif mode == 2:
            o = rdnum(); so += (-1 if o & 1 else 1) * (o >> 1)
            out += src[so:so+ln]; so += ln
        else:
            o = rdnum(); to += (-1 if o & 1 else 1) * (o >> 1)
            for _ in range(ln): out.append(out[to]); to += 1
    if zlib.crc32(bytes(out)) != int.from_bytes(patch[-8:-4], 'little'):
        raise ValueError("target checksum mismatch")
    return bytes(out)

if __name__ == '__main__':
    src = open('Mickey_Mousecapade__USA_.nes','rb').read()
    dst = open('mousecapade_2p_v40.nes','rb').read()
    meta = b''
    bps = create(src, dst, meta)
    open('MickeyMousecapade_2P_Coop_v1.0.bps','wb').write(bps)
    print(f"wrote BPS: {len(bps)} bytes (IPS was 1177)")
    # verify round trip
    assert apply(bps, src) == dst
    print("PASS  BPS applied to the clean ROM reproduces v40 exactly")
    # wrong ROM must be REJECTED, not silently corrupted
    for label, bad in [("headerless ROM", src[16:]), ("already-patched ROM", dst)]:
        try:
            apply(bps, bad); print(f"FAIL  {label} was accepted!")
        except ValueError as e:
            print(f"PASS  {label} rejected -> {e}")
