"""Zhihu `x-zse-96` (v2.0) request signature, pure Python.

Ported from ParseHub (https://github.com/z-mio/ParseHub, MIT License,
Copyright (c) 2024 梓澪), which credits https://github.com/cv-cat/ZhihuApis.

Pipeline:
1. source = "+".join([x-zse-93, path?query, d_c0])
2. digest = md5(source) (hex)
3. plain  = ascii(digest[14:]) with PKCS#7 padding
4. cipher = SM4-CBC(plain, fixed round keys, random 16-byte IV)
5. sig    = custom_base64(iv + cipher)
6. x-zse-96 = "2.0_" + sig
"""

import hashlib
import os
from urllib.parse import urlparse

# --- SM4 constants (extracted from other.js VM) ---------------------------------
SM4_ZB = [
    20,
    223,
    245,
    7,
    248,
    2,
    194,
    209,
    87,
    6,
    227,
    253,
    240,
    128,
    222,
    91,
    237,
    9,
    125,
    157,
    230,
    93,
    252,
    205,
    90,
    79,
    144,
    199,
    159,
    197,
    186,
    167,
    39,
    37,
    156,
    198,
    38,
    42,
    43,
    168,
    217,
    153,
    15,
    103,
    80,
    189,
    71,
    191,
    97,
    84,
    247,
    95,
    36,
    69,
    14,
    35,
    12,
    171,
    28,
    114,
    178,
    148,
    86,
    182,
    32,
    83,
    158,
    109,
    22,
    255,
    94,
    238,
    151,
    85,
    77,
    124,
    254,
    18,
    4,
    26,
    123,
    176,
    232,
    193,
    131,
    172,
    143,
    142,
    150,
    30,
    10,
    146,
    162,
    62,
    224,
    218,
    196,
    229,
    1,
    192,
    213,
    27,
    110,
    56,
    231,
    180,
    138,
    107,
    242,
    187,
    54,
    120,
    19,
    44,
    117,
    228,
    215,
    203,
    53,
    239,
    251,
    127,
    81,
    11,
    133,
    96,
    204,
    132,
    41,
    115,
    73,
    55,
    249,
    147,
    102,
    48,
    122,
    145,
    106,
    118,
    74,
    190,
    29,
    16,
    174,
    5,
    177,
    129,
    63,
    113,
    99,
    31,
    161,
    76,
    246,
    34,
    211,
    13,
    60,
    68,
    207,
    160,
    65,
    111,
    82,
    165,
    67,
    169,
    225,
    57,
    112,
    244,
    155,
    51,
    236,
    200,
    233,
    58,
    61,
    47,
    100,
    137,
    185,
    64,
    17,
    70,
    234,
    163,
    219,
    108,
    170,
    166,
    59,
    149,
    52,
    105,
    24,
    212,
    78,
    173,
    45,
    0,
    116,
    226,
    119,
    136,
    206,
    135,
    175,
    195,
    25,
    92,
    121,
    208,
    126,
    139,
    3,
    75,
    141,
    21,
    130,
    98,
    241,
    40,
    154,
    66,
    184,
    49,
    181,
    46,
    243,
    88,
    101,
    183,
    8,
    23,
    72,
    188,
    104,
    179,
    210,
    134,
    250,
    201,
    164,
    89,
    216,
    202,
    220,
    50,
    221,
    152,
    140,
    33,
    235,
    214,
]
# Pre-expanded 32 SM4 round keys (already derived from the fixed encryption key).
SM4_ZK = [
    k & 0xFFFFFFFF
    for k in [
        1170614578,
        1024848638,
        1413669199,
        -343334464,
        -766094290,
        -1373058082,
        -143119608,
        -297228157,
        1933479194,
        -971186181,
        -406453910,
        460404854,
        -547427574,
        -1891326262,
        -1679095901,
        2119585428,
        -2029270069,
        2035090028,
        -1521520070,
        -5587175,
        -77751101,
        -2094365853,
        -1243052806,
        1579901135,
        1321810770,
        456816404,
        -1391643889,
        -229302305,
        330002838,
        -788960546,
        363569021,
        -1947871109,
    ]
]

# --- custom base64 constants (extracted / solved from other.js) -----------------
ALPHABET = "6fpLRqJO8M/c3jnYxFkUVC4ZIG12SiH=5v0mXDazWBTsuw7QetbKdoPyAl+hN9rgE"
# per-sextet XOR mask, period 16 groups, repeated 4 times over the 64 output chars
MASKS = [58, 0, 0, 0, 0, 40, 3, 0, 0, 0, 32, 14, 0, 0, 0, 0] * 4

ZSE93 = "101_3_3.0"


def _u32(x):
    return x & 0xFFFFFFFF


def _rotl(x, n):
    return _u32((x << n) | (x >> (32 - n)))


def _load_be(arr, o):
    return _u32((arr[o] << 24) | (arr[o + 1] << 16) | (arr[o + 2] << 8) | arr[o + 3])


def _store_be(v, arr, o):
    arr[o] = (v >> 24) & 255
    arr[o + 1] = (v >> 16) & 255
    arr[o + 2] = (v >> 8) & 255
    arr[o + 3] = v & 255


def _tau_l(x):
    b = [(x >> 24) & 255, (x >> 16) & 255, (x >> 8) & 255, x & 255]
    t = [SM4_ZB[b[0]], SM4_ZB[b[1]], SM4_ZB[b[2]], SM4_ZB[b[3]]]
    ec = _load_be(t, 0)
    return _u32(ec ^ _rotl(ec, 2) ^ _rotl(ec, 10) ^ _rotl(ec, 18) ^ _rotl(ec, 24))


def _sm4_encrypt_block(block):
    out = [0] * 16
    x = [0] * 36
    x[0] = _load_be(block, 0)
    x[1] = _load_be(block, 4)
    x[2] = _load_be(block, 8)
    x[3] = _load_be(block, 12)
    for i in range(32):
        x[i + 4] = _u32(x[i] ^ _tau_l(x[i + 1] ^ x[i + 2] ^ x[i + 3] ^ SM4_ZK[i]))
    _store_be(x[35], out, 0)
    _store_be(x[34], out, 4)
    _store_be(x[33], out, 8)
    _store_be(x[32], out, 12)
    return out


def _sm4_cbc(data, iv):
    result = []
    prev = list(iv)
    for off in range(0, len(data), 16):
        block = data[off : off + 16]
        xored = [block[i] ^ prev[i] for i in range(16)]
        prev = _sm4_encrypt_block(xored)
        result.extend(prev)
    return result


def _pkcs7(data, block=16):
    pad = block - (len(data) % block)
    return list(data) + [pad] * pad


def _custom_b64(blob):
    # 48 bytes -> 384 bits -> 64 sextets
    bits = []
    for b in blob:
        for j in range(8):
            bits.append((b >> (7 - j)) & 1)
    in_sext = []
    for k in range(64):
        v = 0
        for j in range(6):
            v = (v << 1) | bits[6 * k + j]
        in_sext.append(v)
    out = []
    for g in range(64):
        out.append(ALPHABET[in_sext[63 - g] ^ MASKS[g]])
    return "".join(out)


def zhihu_encrypt(digest, iv=None):
    """Encrypt a 32-char md5 hex string, returning the base64 signature body.

    ``iv`` (16 bytes) is prepended to the ciphertext; the server recovers it, so
    any value works. Defaults to random bytes to mimic the browser.
    """
    if iv is None:
        iv = list(os.urandom(16))
    else:
        iv = list(iv)
    plain = _pkcs7([ord(c) for c in digest[14:]])
    cipher = _sm4_cbc(plain, iv)
    return _custom_b64(iv + cipher)


def encrypt_md5(source, iv=None):
    """md5(source) then encrypt -> signature body (without the ``2.0_`` prefix)."""
    digest = hashlib.md5(source.encode("utf-8")).hexdigest()
    return zhihu_encrypt(digest, iv=iv)


def get_x_zse_96(url: str, d_c0: str, iv=None) -> str:
    """Compute the `x-zse-96` header for a request URL (query included, exactly as sent)."""
    parsed = urlparse(url)
    path = parsed.path + (("?" + parsed.query) if parsed.query else "")
    source = "+".join([ZSE93, path, d_c0])
    return "2.0_" + encrypt_md5(source, iv=iv)
