# Code-free streaming packet identity clarification

This is a description of the existing frozen producer contract, not a new algorithm or a source change. It was clarified for independent auditor compatibility before actual fitting. Only packet_sha256 uses this stream; ordinary numeric checkpoint/schema/result hashes retain their separately documented canonical numeric-JSON encoding.

Compute SHA256 over the following concatenated depth-first byte stream, without a wrapper, newline, implicit length prefix or extra separator:

1. A native ndarray contributes ASCII A, then canonical JSON bytes for {dtype: actual dtype.str, shape: integer dimension list}, then raw array bytes in C order. There is no array end marker. Retain original dtype/endian bytes; do not convert to another dtype, normalize floating bits, or use __array__/hex JSON here.
2. A dictionary contributes ASCII D. Visit keys in Python's sorted-string order (no Unicode normalization). For each key, append canonical JSON of the key itself, without a V marker, then stream its value recursively. Append ASCII E after the last pair.
3. A list or tuple contributes ASCII L, each element recursively in order, then ASCII E. These two sequence types deliberately have the same stream representation.
4. Every allowed scalar contributes ASCII V followed by canonical JSON bytes of that scalar.

Canonical JSON here means Python json.dumps with sort_keys=True, separators comma/colon without spaces, allow_nan=False and default ensure_ascii=True, encoded as UTF-8 without a newline. Keys/strings carry normal JSON quotes/escapes; non-ASCII characters use JSON escapes. Booleans are true/false, None is null, integers decimal, and finite floats use Python's JSON float representation, retaining -0.0 where supplied. Arrays are validated native finite arrays before packet identity is used. Header keys therefore serialize in dtype,shape order. The packet stream itself does not introduce the numeric snapshot's array marker/hex fields.

These manually specified tiny byte streams and SHA256 vectors are independent of importing producer code, Torch or real packets:

- None: stream_hex=566e756c6c, SHA256=81ea3b9b1a9442841824adb002ce5b98734bb43b663c034b20e5eb3f35da81ce
- empty dictionary: stream_hex=4445, SHA256=6814ef46f686990cf4e946f966167b0507e1d642c44e51f61bffb0bba2d4672b
- list containing empty tuple: stream_hex=4c4c4545, SHA256=271b2622fc45df7f4ffea9e8bfb56b48e444834843eba0e306f3eeeb8d6739c8
- dictionary a=unicode e-acute and b=[1,false]: stream_hex=4422612256225c7530306539222262224c56315666616c73654545, SHA256=f9c46eff5bf0ce5ce7ee6d4230e4f8cc890aa45f8400f3b33229c29fcfa30ba6
- float64 array shape2 values1.0,-0.0: stream_hex=417b226474797065223a223c6638222c227368617065223a5b325d7d000000000000f03f0000000000000080, SHA256=690472a9bd36b1f0a34708d88b54fe12c252592babe7d3c73a7394666842ba5a
- uint8 empty array shape0: stream_hex=417b226474797065223a227c7531222c227368617065223a5b305d7d, SHA256=f00bb81cefe318f4bfae8121d17dd229a3d80d93fbf584895d4a5027a8c6626f

Producer source provenance: frozen processor.py33997bytes SHA25659b8c4160f0bc16821ca2b5bafe2a5900022449010d026182dc2f5883afeb5af; numeric_state.py SHA256acd9f95510b5b2d990f9ff36a0ad1450474dd6d1a12e4b5d2de679d9599a6d03. No implementation listing is included so the independent auditor can reproduce the public contract without reading producer implementation.
