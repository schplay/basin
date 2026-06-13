"""GStreamer pipeline builder for AES-67 multicast RTP capture.

Pipelines are constructed as GStreamer description strings and launched via
gi.repository.Gst. Each source gets one pipeline that handles both recording
(per-channel filesinks) and metering (level element posting bus messages).
"""
from __future__ import annotations

from pathlib import Path

# Encoding name → RTP depayloader element name
_DEPAY_MAP = {
    "L24": "rtpL24depay",
    "L16": "rtpL16depay",
}

# (bit_depth, container) → (GStreamer sink element, file extension)
_SINK_MAP: dict[tuple[int, str], tuple[str, str]] = {
    (16, "wav"):  ("wavenc", ".wav"),
    (24, "wav"):  ("wavenc", ".wav"),
    (32, "wav"):  ("wavenc", ".wav"),
    (16, "aiff"): ("aiffenc", ".aif"),
    (24, "aiff"): ("aiffenc", ".aif"),
    (24, "rf64"): ("wavenc", ".wav"),   # rf64 auto-promoted post-write via mutagen
    (32, "rf64"): ("wavenc", ".wav"),
}

_FORMAT_MAP = {
    16: "S16BE",
    24: "S24BE",
    32: "S32BE",
}

_OUT_FORMAT_MAP = {
    16: "S16LE",
    24: "S24LE",
    32: "S32LE",
}


def build_record_pipeline(
    multicast_address: str,
    rtp_port: int,
    network_interface: str,
    source_channel_count: int,
    channels_to_record: list[dict],
    recording_path: Path,
    sample_rate: int,
    bit_depth: int,
    container: str,
    encoding_name: str = "L24",
) -> str:
    """Return a GStreamer pipeline description string for recording.

    channels_to_record: list of {channel_number, source_channel, source_id, filename}
      where filename is the pre-rendered output filename (stem + ext).

    The pipeline:
      udpsrc → rtpjitterbuffer → rtpL24depay → audioconvert → tee
        branch 0: deinterleave → per-channel sinks (recording)
        branch 1: level → fakesink (metering)
    """
    depay = _DEPAY_MAP.get(encoding_name, "rtpL24depay")
    sink_elem, _ = _SINK_MAP.get((bit_depth, container), ("wavenc", ".wav"))
    raw_fmt = _FORMAT_MAP.get(bit_depth, "S24BE")
    out_fmt = _OUT_FORMAT_MAP.get(bit_depth, "S24LE")
    n = source_channel_count

    # Index channels by their 0-based source_channel position
    channel_by_src: dict[int, dict] = {
        ch["source_channel"] - 1: ch for ch in channels_to_record
    }

    parts: list[str] = []

    # Source and depayloader
    parts.append(
        f'udpsrc multicast-group={multicast_address} port={rtp_port}'
        f' multicast-iface={network_interface}'
        f' caps="application/x-rtp, media=audio, encoding-name={encoding_name},'
        f' channels={n}, clock-rate={sample_rate}"'
    )
    parts.append(f'! rtpjitterbuffer latency=20 do-lost=true')
    parts.append(f'! {depay}')
    parts.append(
        f'! audio/x-raw, format={raw_fmt}, channels={n}, rate={sample_rate}'
    )
    parts.append('! audioconvert')
    parts.append('! tee name=t')

    # Recording branch: deinterleave → per-channel sinks
    parts.append('t. ! queue ! deinterleave name=di')

    for src_idx in range(n):
        ch = channel_by_src.get(src_idx)
        if ch is not None:
            out_path = str(recording_path / ch["filename"])
            parts.append(
                f'di.src_{src_idx} ! queue'
                f' ! audioconvert ! audio/x-raw,format={out_fmt}'
                f' ! {sink_elem} ! filesink location="{out_path}"'
            )
        else:
            # Channel not selected for this recording — discard
            parts.append(f'di.src_{src_idx} ! queue ! fakesink sync=false')

    # Metering branch: level element posts bus messages at ~4 Hz (250 ms interval)
    # interval is in nanoseconds
    parts.append(
        't. ! queue ! audioconvert'
        ' ! level name=lvl interval=250000000 post-messages=true'
        ' ! fakesink sync=false'
    )

    return ' '.join(parts)


def build_meter_only_pipeline(
    multicast_address: str,
    rtp_port: int,
    network_interface: str,
    channel_count: int,
    sample_rate: int,
    bit_depth: int,
    encoding_name: str = "L24",
) -> str:
    """Pipeline for metering without recording (pre-recording monitor or source status)."""
    depay = _DEPAY_MAP.get(encoding_name, "rtpL24depay")
    raw_fmt = _FORMAT_MAP.get(bit_depth, "S24BE")

    return (
        f'udpsrc multicast-group={multicast_address} port={rtp_port}'
        f' multicast-iface={network_interface}'
        f' caps="application/x-rtp, media=audio, encoding-name={encoding_name},'
        f' channels={channel_count}, clock-rate={sample_rate}"'
        f' ! rtpjitterbuffer latency=20 do-lost=true'
        f' ! {depay}'
        f' ! audio/x-raw, format={raw_fmt}, channels={channel_count}, rate={sample_rate}'
        f' ! audioconvert'
        f' ! level name=lvl interval=250000000 post-messages=true'
        f' ! fakesink sync=false'
    )
