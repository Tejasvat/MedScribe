
from io import BytesIO

from datasets import Audio, load_dataset
import soundfile as sf


def main() -> None:
    """Download the first dataset recording and export it as a WAV file."""
    # Streaming avoids downloading the complete dataset just to export one clip.
    ds = load_dataset("piyushmaharana/primock57", split="train", streaming=True)

    print("Streaming the first recording from piyushmaharana/primock57")
    print("Available columns:", ds.column_names)

    # Keep the source audio as bytes so this works without torchcodec.
    ds = ds.cast_column("audio", Audio(decode=False))
    sample = next(iter(ds))
    audio_bytes = sample["audio"]["bytes"]
    if audio_bytes is None:
        raise ValueError("The selected recording does not contain embedded audio bytes.")

    audio_array, sampling_rate = sf.read(BytesIO(audio_bytes))
    sf.write("consultation.wav", audio_array, sampling_rate)

    print("Saved consultation.wav")
    print("Filename:", sample.get("file_name"))
    print("Reference transcript:", sample.get("transcript"))


if __name__ == "__main__":
    main()
