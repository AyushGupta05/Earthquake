# Official archive formatter source audit v1

The bounded trail found an official **reader configuration**, not the archive writer. It supports a separately versioned literal-key transport hypothesis. It does not establish why the earlier four candidates failed or whether their waveforms exist. Root reports four HTTP404/NoSuchKey outcomes; no actual keys, metadata, objects or private receipts were read here.

## Supported source convention and limits

| Question | Verified public source | Limit / unknown |
|---|---|---|
| Filename fields | GEONET config orders `year.DOY.STATION.LOCATION-CHANNEL.NETWORK.D`, beneath `waveforms/miniseed/year/year.DOY/STATION.NETWORK/`. [Pinned config](https://github.com/GeoNet/geonet-obspy-utils/blob/5bce92270ba19f30bf8829cdcb471e3a3d28fad7/geonet_obspy_utils/clients/aws/client_config.yml#L1-L7) | Reader configuration is not a deployed writer or selected-object proof. |
| UTC/day | Client requires `UTCDateTime`, formats `.year`/`.julday`, and advances at UTC midnight. [Pinned client](https://github.com/GeoNet/geonet-obspy-utils/blob/5bce92270ba19f30bf8829cdcb471e3a3d28fad7/geonet_obspy_utils/clients/aws/client.py#L169-L229) | Supports its UTC querying convention; writer partition rules remain unverified. |
| NSLC / LC | Client splits comma fields and strips them before substitution, then lists and matches holdings. [Pinned client](https://github.com/GeoNet/geonet-obspy-utils/blob/5bce92270ba19f30bf8829cdcb471e3a3d28fad7/geonet_obspy_utils/clients/aws/client.py#L177-L222) | No certified stored blank-LC rule or special `--` conversion. The proposal uses literal nonblank LC2 and no normalization. |
| Endpoint / access | Config declares `https://geonet-open-data.s3.ap-southeast-2.amazonaws.com`; client configures unsigned SDK access. [Config](https://github.com/GeoNet/geonet-obspy-utils/blob/5bce92270ba19f30bf8829cdcb471e3a3d28fad7/geonet_obspy_utils/clients/aws/client_config.yml#L1-L7), [client](https://github.com/GeoNet/geonet-obspy-utils/blob/5bce92270ba19f30bf8829cdcb471e3a3d28fad7/geonet_obspy_utils/clients/aws/client.py#L69-L85) | No live HTTPS mapping, permissions, requester-pays or selected-object availability was tested. |
| Coverage / freshness | Official access page states daily sync and directs near-real-time use elsewhere. [GeoNet AWS access](https://www.geonet.org.nz/data/access/aws) | No explicit historical coverage/retention/completeness guarantee was found. |
| Route | Official waveform page recommends supported FDSN access and AWS for large continuous volumes. [GeoNet seismic waveforms](https://www.geonet.org.nz/data/types/seismic_waveforms) | This is route guidance, not a coverage or latency guarantee. |

The configured field order differs from the earlier pinned tutorial's `STATION.NETWORK-CHANNEL.LOCATION` filename order. This is a source-level discrepancy. No actual candidate was compared, and no deployment or conversion fault is inferred. [Earlier official tutorial](https://github.com/GeoNet/data-tutorials/blob/db4574a7b230a5a820c5419bd0234d0bed642184/AWS_Open_Data/README.md#miniseed-waveform-data)

## Conditional next step

Freeze a NEW four-slot plan using only this configured field order, the same prior TRAIN/DEV roster and reference clocks, and unchanged numerical transport limits. Retain `mapping_status: unverified_hypothesis` and the uncertainties in [CONFIGURED_TEMPLATE.json](CONFIGURED_TEMPLATE.json). A new HTTP200 body would establish only bounded literal transport; a new failure would not distinguish day, channel, location, endpoint or coverage causes. No alias trials, listing, replacement, fallback, scientific decoding or repair of the failed96/V2 outcomes follows from this audit. The exact generic proposal is [PROSPECTIVE_FOUR_SLOT.md](PROSPECTIVE_FOUR_SLOT.md).

## Provenance / scope

The utility revision is `5bce92270ba19f30bf8829cdcb471e3a3d28fad7`; its root tree is `795fbb5a7e8cc4c639bdfd0dffc2383a8c1df98c`. Inert blob decoding and Git-object hashing verified exact source bytes and tree membership. No downloaded module was executed/imported. License text was not retrieved; raw sources/HTML/API responses/headers are excluded from the curated packet. Six focused discovery queries and ten bounded source/document GETs exhaust this trail; it is not an exhaustive search of historical GeoNet repositories. See [REQUEST_SCOPE_LEDGER.md](REQUEST_SCOPE_LEDGER.md) and [SOURCE_PINS.json](SOURCE_PINS.json).
