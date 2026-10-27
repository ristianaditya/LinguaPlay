"""Unity Localization string tables (StringTable MonoBehaviours) inside UnityFS asset bundles.

Only English tables are exposed, so translated text appears when the game runs in English. The bundle
is rebuilt with uncompressed blocks; every object except the edited string tables is copied byte for
byte, and each edited table is re-serialized from its type tree (round-trip verified before use).
Addressables bundles with a CRC in the catalog would be rejected by Unity; see `catalog_crc`.
"""
from pathlib import Path
import re
import struct
from .adapters import Entry, digest, register_adapter

MAX_BUNDLE_SIZE = 64 * 1024 * 1024
BUNDLE_NAME = re.compile(r'(string|locali[sz]ation|table)', re.I)


def lz4_block(data, size):
    out = bytearray(); pos = 0; end = len(data)
    while pos < end:
        token = data[pos]; pos += 1
        length = token >> 4
        if length == 15:
            while True:
                extra = data[pos]; pos += 1; length += extra
                if extra != 255: break
        out += data[pos:pos + length]; pos += length
        if pos >= end: break
        offset = data[pos] | data[pos + 1] << 8; pos += 2
        if not offset or offset > len(out): raise ValueError('Data LZ4 rusak.')
        length = token & 15
        if length == 15:
            while True:
                extra = data[pos]; pos += 1; length += extra
                if extra != 255: break
        length += 4; start = len(out) - offset
        if length <= offset: out += out[start:start + length]
        else:
            for i in range(length): out.append(out[start + i])
    if len(out) != size: raise ValueError('Ukuran LZ4 tidak cocok.')
    return bytes(out)


def _decompress(data, flags, size):
    kind = flags & 0x3F
    if kind == 0: return data
    if kind in (2, 3): return lz4_block(data, size)
    raise ValueError('Kompresi bundle (LZMA) belum didukung.')


def _cstr(data, pos):
    end = data.index(b'\0', pos); return data[pos:end].decode('utf-8'), end + 1


class Bundle:
    def __init__(self, raw):
        if not raw.startswith(b'UnityFS\0'): raise ValueError('Bukan bundle UnityFS.')
        self.raw = raw; pos = 8
        self.format = struct.unpack_from('>I', raw, pos)[0]; pos += 4
        self.player, pos = _cstr(raw, pos); self.engine, pos = _cstr(raw, pos)
        total, csize, usize, self.flags = struct.unpack_from('>QIII', raw, pos); pos += 20
        if self.format < 6 or self.format > 8: raise ValueError('Versi UnityFS belum didukung.')
        if self.format >= 7: pos = (pos + 15) // 16 * 16
        header_end = pos
        if self.flags & 0x80: info = raw[len(raw) - csize:]; data_start = header_end
        else: info = raw[pos:pos + csize]; data_start = pos + csize
        info = _decompress(info, self.flags, usize); p = 16
        count = struct.unpack_from('>i', info, p)[0]; p += 4; blocks = []
        for _ in range(count):
            bu, bc, bf = struct.unpack_from('>IIH', info, p); p += 10; blocks.append((bu, bc, bf))
        nodes = []; node_count = struct.unpack_from('>i', info, p)[0]; p += 4
        for _ in range(node_count):
            offset, size, node_flags = struct.unpack_from('>qqI', info, p); p += 20
            name, p = _cstr(info, p); nodes.append([offset, size, node_flags, name])
        if self.flags & 0x200: data_start = (data_start + 15) // 16 * 16
        stream = bytearray(); cursor = data_start
        for bu, bc, bf in blocks:
            stream += _decompress(raw[cursor:cursor + bc], bf, bu); cursor += bc
        self.header_size = header_end; self.nodes = nodes; self.data = bytes(stream)

    def file(self, name):
        node = next(n for n in self.nodes if n[3] == name); return self.data[node[0]:node[0] + node[1]]

    def rebuild(self, replacements):
        if not replacements: return self.raw
        stream = bytearray(); nodes = []
        for offset, size, flags, name in self.nodes:
            data = replacements.get(name, self.data[offset:offset + size]); nodes.append((len(stream), len(data), flags, name)); stream += data
        block_size = 1 << 17; blocks = [(min(block_size, len(stream) - i), min(block_size, len(stream) - i), 0) for i in range(0, len(stream), block_size)] or [(0, 0, 0)]
        info = b'\0' * 16 + struct.pack('>i', len(blocks)) + b''.join(struct.pack('>IIH', *b) for b in blocks)
        info += struct.pack('>i', len(nodes)) + b''.join(struct.pack('>qqI', o, s, f) + n.encode() + b'\0' for o, s, f, n in nodes)
        flags = (self.flags & ~0x3F & ~0x80) | 0x40   # uncompressed info, stored right after the header
        head = bytearray(b'UnityFS\0' + struct.pack('>I', self.format) + self.player.encode() + b'\0' + self.engine.encode() + b'\0' + b'\0' * 20)
        if self.format >= 7: head += b'\0' * (-len(head) % 16)
        body_start = len(head) + len(info)
        padding = b'\0' * (-body_start % 16) if flags & 0x200 else b''
        total = body_start + len(padding) + len(stream)
        fixed = 8 + 4 + len(self.player) + 1 + len(self.engine) + 1
        struct.pack_into('>QIII', head, fixed, total, len(info), len(info), flags)
        return bytes(head) + info + padding + bytes(stream)


class TypeNode:
    __slots__ = ('type', 'name', 'size', 'flags', 'children')
    def __init__(self, type_, name, size, flags):
        self.type, self.name, self.size, self.flags, self.children = type_, name, size, flags, []

def parse_type_tree(blob, pos, version):
    count, buffer_size = struct.unpack_from('<ii', blob, pos); pos += 8
    stride = 32 if version >= 19 else 24
    raw_nodes = [struct.unpack_from('<HBBIIiiI', blob, pos + i * stride) for i in range(count)]
    pos += count * stride; strings = blob[pos:pos + buffer_size]; pos += buffer_size
    def text(offset):
        if offset & 0x80000000: return COMMON.get(offset & 0x7FFFFFFF, f'#{offset & 0x7FFFFFFF}')
        end = strings.index(b'\0', offset); return strings[offset:end].decode('utf-8')
    root = None; stack = []
    for _, level, _, type_offset, name_offset, size, _, meta in raw_nodes:
        node = TypeNode(text(type_offset), text(name_offset), size, meta)
        while len(stack) > level: stack.pop()
        if stack: stack[-1].children.append(node)
        else: root = node
        stack.append(node)
    return root, pos

# Offsets into Unity's common string buffer (stable since Unity 5).
COMMON = {0: 'AABB', 5: 'AnimationClip', 19: 'AnimationCurve', 34: 'AnimationState', 49: 'Array', 55: 'Base', 60: 'BitField', 69: 'bitset',
          76: 'bool', 81: 'char', 86: 'ColorRGBA', 96: 'Component', 106: 'data', 111: 'deque', 117: 'double', 124: 'dynamic_array',
          138: 'FastPropertyName', 155: 'first', 161: 'float', 167: 'Font', 172: 'GameObject', 183: 'Generic Mono', 196: 'GradientNEW',
          208: 'GUID', 213: 'GUIStyle', 222: 'int', 226: 'list', 231: 'long long', 241: 'map', 245: 'Matrix4x4f', 256: 'MdFour',
          263: 'MonoBehaviour', 277: 'MonoScript', 288: 'm_ByteSize', 299: 'm_Curve', 307: 'm_EditorClassIdentifier', 331: 'm_EditorHideFlags',
          349: 'm_Enabled', 359: 'm_ExtensionPtr', 374: 'm_GameObject', 387: 'm_Index', 395: 'm_IsArray', 405: 'm_IsStatic', 416: 'm_MetaFlag',
          427: 'm_Name', 434: 'm_ObjectHideFlags', 452: 'm_PrefabInternal', 469: 'm_PrefabParentObject', 490: 'm_Script',
          499: 'm_StaticEditorFlags', 519: 'm_Type', 526: 'm_Version', 536: 'Object', 543: 'pair', 548: 'PPtr<Component>',
          564: 'PPtr<GameObject>', 581: 'PPtr<Material>', 596: 'PPtr<MonoBehaviour>', 616: 'PPtr<MonoScript>', 633: 'PPtr<Object>',
          646: 'PPtr<Prefab>', 659: 'PPtr<Sprite>', 672: 'PPtr<TextAsset>', 688: 'PPtr<Texture>', 702: 'PPtr<Texture2D>',
          718: 'PPtr<Transform>', 734: 'Prefab', 741: 'Quaternionf', 753: 'Rectf', 759: 'RectInt', 767: 'RectOffset', 778: 'second',
          785: 'set', 789: 'short', 795: 'size', 800: 'SInt16', 807: 'SInt32', 814: 'SInt64', 821: 'SInt8', 827: 'staticvector',
          840: 'string', 847: 'TextAsset', 857: 'TextMesh', 866: 'Texture', 874: 'Texture2D', 884: 'Transform', 894: 'TypelessData',
          907: 'UInt16', 914: 'UInt32', 921: 'UInt64', 928: 'UInt8', 934: 'unsigned int', 947: 'unsigned long long', 966: 'unsigned short',
          981: 'vector', 988: 'Vector2f', 997: 'Vector3f', 1006: 'Vector4f', 1015: 'm_ScriptingClassIdentifier', 1042: 'Gradient',
          1051: 'Type*', 1057: 'int2_storage', 1070: 'int3_storage', 1083: 'BoundsInt', 1093: 'm_CorrespondingSourceObject',
          1121: 'm_PrefabInstance', 1138: 'm_PrefabAsset', 1152: 'FileSize', 1161: 'Hash128', 1169: 'RenderingLayerMask'}

PRIMITIVE = {'bool': 1, 'SInt8': 1, 'UInt8': 1, 'char': 1, 'SInt16': 2, 'UInt16': 2, 'short': 2, 'unsigned short': 2,
             'SInt32': 4, 'UInt32': 4, 'int': 4, 'unsigned int': 4, 'float': 4, 'Type*': 4,
             'SInt64': 8, 'UInt64': 8, 'long long': 8, 'unsigned long long': 8, 'double': 8, 'FileSize': 8}


class Unparsed(Exception):
    pass


def walk(node, data, pos, on_string, path=''):
    """Walk serialized data with its type tree; calls on_string(path, start, end) for every string."""
    here = f'{path}/{node.name}'
    if node.type == 'string':
        length = struct.unpack_from('<i', data, pos)[0]
        if length < 0 or pos + 4 + length > len(data): raise ValueError('String Unity tidak valid.')
        on_string(here, pos, pos + 4 + length); pos += 4 + length; pos = (pos + 3) & ~3
    elif node.type == 'TypelessData':
        length = struct.unpack_from('<i', data, pos)[0]; pos += 4 + length
    elif node.children and node.children[0].type == 'Array' or node.type == 'Array':
        array = node if node.type == 'Array' else node.children[0]
        count = struct.unpack_from('<i', data, pos)[0]; pos += 4
        if count < 0 or count > 10_000_000: raise ValueError('Array Unity tidak valid.')
        element = array.children[1]
        if not element.children and element.size > 0 and element.type != 'string':
            pos += element.size * count
        else:
            for index in range(count): pos = walk(element, data, pos, on_string, f'{here}[{index}]')
        if array.flags & 0x4000: pos = (pos + 3) & ~3
    elif not node.children:
        # Leaf: fixed-size primitive; a variable leaf (e.g. ReferencedObjectData) needs another type tree.
        if node.size < 0: raise Unparsed()
        pos += node.size
    else:
        for child in node.children: pos = walk(child, data, pos, on_string, here)
    if node.flags & 0x4000: pos = (pos + 3) & ~3
    return pos


class SerializedFile:
    def __init__(self, data):
        self.data = data
        metadata_size, file_size, version, data_offset = struct.unpack_from('>IIII', data, 0)
        if version < 17 or version > 23: raise ValueError('Versi SerializedFile Unity belum didukung.')
        self.version = version; pos = 20
        if version >= 22:
            metadata_size, file_size, data_offset = struct.unpack_from('>IQQ', data, 20); pos = 48
        if data[16] != 0: raise ValueError('SerializedFile big-endian belum didukung.')
        self.data_offset = data_offset
        self.unity, pos = _cstr(data, pos); pos += 4
        self.typetree = data[pos] != 0; pos += 1
        if not self.typetree: raise ValueError('Bundle tanpa type tree belum didukung.')
        type_count = struct.unpack_from('<i', data, pos)[0]; pos += 4; self.types = []
        for _ in range(type_count):
            class_id = struct.unpack_from('<i', data, pos)[0]; pos += 4 + 1 + 2
            if class_id == 114: pos += 16
            pos += 16
            root, pos = parse_type_tree(data, pos, version)
            if version >= 21:
                deps = struct.unpack_from('<i', data, pos)[0]; pos += 4 + 4 * deps
            self.types.append((class_id, root))
        object_count = struct.unpack_from('<i', data, pos)[0]; pos += 4; self.objects = []
        for _ in range(object_count):
            pos = (pos + 3) & ~3
            path_id = struct.unpack_from('<q', data, pos)[0]; pos += 8
            field = pos
            if version >= 22: start = struct.unpack_from('<Q', data, pos)[0]; pos += 8
            else: start = struct.unpack_from('<I', data, pos)[0]; pos += 4
            size, type_index = struct.unpack_from('<Ii', data, pos); pos += 8
            self.objects.append({'path_id': path_id, 'start': start, 'size': size, 'type': type_index, 'field': field})

    def object_data(self, obj):
        start = self.data_offset + obj['start']; return self.data[start:start + obj['size']]

    def rebuild(self, replacements):
        """replacements: {path_id: new object bytes}; objects keep their order, aligned to 8 bytes."""
        head = bytearray(self.data[:self.data_offset]); body = bytearray()
        for obj in sorted(self.objects, key=lambda o: o['start']):
            body += b'\0' * (-len(body) % 8)
            data = replacements.get(obj['path_id'], self.object_data(obj)); start = len(body); body += data
            if self.version >= 22: struct.pack_into('<QI', head, obj['field'], start, len(data))
            else: struct.pack_into('<II', head, obj['field'], start, len(data))
        total = len(head) + len(body)
        if self.version >= 22: struct.pack_into('>Q', head, 24, total)
        else: struct.pack_into('>I', head, 4, total)
        return bytes(head) + bytes(body)


def _has_table(node):
    names = {c.name for c in node.children}
    return 'm_TableData' in names and 'm_LocaleId' in names


class UnityStringTableDocument:
    format = 'Unity Localization (StringTable)'

    def __init__(self, path, raw, bundle, assets):
        """assets: [(node name, SerializedFile, [(object, rows)])]; rows: [(entry id, text, start, end)]."""
        self.path = Path(path); self.raw = raw; self.bundle = bundle; self.assets = assets
        self.entries = []; self.locations = {}
        for node_name, serialized, tables in assets:
            for obj, rows in tables:
                for entry_id, text, start, end in rows:
                    identity = f'{obj["path_id"]:x}:{entry_id}'
                    if identity in self.locations or not text.strip() or not any(c.isalpha() for c in text): continue
                    self.entries.append(Entry(identity, text)); self.locations[identity] = (node_name, obj['path_id'], start, end)

    @property
    def sha256(self):
        return digest(self.raw)

    def check_translation(self, entry_id, value):
        if not isinstance(value, str) or not value.strip() or '\x00' in value: raise ValueError('Terjemahan kosong atau tidak valid.')

    def render(self, translations):
        if set(translations) - set(self.locations): raise ValueError('ID terjemahan tidak dikenal.')
        if not translations: return self.raw
        edits = {}
        for entry_id, value in translations.items():
            self.check_translation(entry_id, value); node, path_id, start, end = self.locations[entry_id]
            edits.setdefault(node, {}).setdefault(path_id, []).append((start, end, value))
        files = {}
        for node_name, serialized, tables in self.assets:
            if node_name not in edits: continue
            changed = {}
            for obj, _ in tables:
                spans = edits[node_name].get(obj['path_id'])
                if not spans: continue
                data = serialized.object_data(obj); out = bytearray(); cursor = 0
                for start, end, value in sorted(spans):
                    encoded = value.encode('utf-8'); padded_end = (end + 3) & ~3
                    out += data[cursor:start] + struct.pack('<i', len(encoded)) + encoded; out += b'\0' * (-len(out) % 4); cursor = padded_end
                out += data[cursor:]; changed[obj['path_id']] = bytes(out)
            files[node_name] = serialized.rebuild(changed)
        return self.bundle.rebuild(files)


def read_string_tables(serialized):
    tables = []
    for obj in serialized.objects:
        class_id, root = serialized.types[obj['type']]
        if class_id != 114 or not _has_table(root): continue
        data = serialized.object_data(obj); strings = []
        try:
            walk(root, data, 0, lambda path, start, end: strings.append((path, start, end)))
        except Unparsed:
            pass   # managed references follow the table data; strings before them are complete
        except (ValueError, struct.error, IndexError):
            continue
        locale = next((data[s + 4:e].decode('utf-8', 'ignore') for p, s, e in strings if p.endswith('m_LocaleId/m_Code')), '')
        if not locale.lower().startswith('en'): continue
        rows = []
        for path, start, end in strings:
            match = re.search(r'/m_TableData\[(\d+)\](?:/data)?/m_Localized$', path)
            if match: rows.append((match.group(1), data[start + 4:end].decode('utf-8', 'replace'), start, end))
        # AssetTables use the same layout but hold asset GUIDs ("389fd902…"), which must never be translated.
        guid = re.compile(r'^[0-9a-f]{32}(\[[^\]]*\])?$')
        rows = [row for row in rows if not guid.match(row[1].strip())]
        if rows: tables.append((obj, rows))
    return tables


def read_unity_bundle(path):
    path = Path(path)
    if not BUNDLE_NAME.search(path.name): raise ValueError('Bundle ini bukan tabel teks.')
    with path.open('rb') as stream:
        if stream.read(8) != b'UnityFS\0': raise ValueError('Bukan bundle UnityFS.')
    raw = path.read_bytes(); bundle = Bundle(raw); assets = []
    for offset, size, flags, name in bundle.nodes:
        if name.endswith(('.resS', '.resource')) or not flags & 4: continue
        try: serialized = SerializedFile(bundle.file(name))
        except (ValueError, struct.error, IndexError): continue
        tables = read_string_tables(serialized)
        if tables: assets.append((name, serialized, tables))
    if not assets: raise ValueError('Bundle ini tidak berisi tabel teks bahasa Inggris (Unity Localization).')
    return UnityStringTableDocument(path, raw, bundle, assets)

register_adapter('unity-string-table', ('.bundle',), read_unity_bundle, max_size=MAX_BUNDLE_SIZE)
