import h5py
import glob
import torch
import numpy as np
import os
import torchaudio
import soundfile as sf
from utils.g2p.symbols import symbols
from utils.g2p import PhonemeBpeTokenizer
from utils.prompt_making import make_prompt, make_transcript
from data.collation import get_text_token_collater
from data.dataset import create_dataloader

# Mappings from symbol to numeric ID and vice versa:
_symbol_to_id = {s: i for i, s in enumerate(symbols)}
_id_to_symbol = {i: s for i, s in enumerate(symbols)}
from data.tokenizer import (
    AudioTokenizer,
    tokenize_audio,
)

tokenizer_path = "./utils/g2p/bpe_69.json"
tokenizer = PhonemeBpeTokenizer(tokenizer_path)
device = 'cuda' if torch.cuda.is_available() else 'cpu'

def make_prompts(name, audio_prompt_path, transcript=None, cleaner="cje_cleaners"):
    text_tokenizer = PhonemeBpeTokenizer(tokenizer_path="./utils/g2p/bpe_69.json", cleaner=cleaner)
    text_collater = get_text_token_collater()
    codec = AudioTokenizer(device)
    wav_pr, sr = torchaudio.load(audio_prompt_path)
    # check length
    if wav_pr.size(-1) / sr > 15:
        raise ValueError(f"Prompt too long, expect length below 15 seconds, got {wav_pr / sr} seconds.")
    if wav_pr.size(0) == 2:
        wav_pr = wav_pr.mean(0, keepdim=True)
    text_pr, lang_pr = make_transcript(name, wav_pr, sr, transcript)

    if transcript:
      text_pr = transcript

    # tokenize audio
    encoded_frames = tokenize_audio(codec, (wav_pr, sr))
    audio_tokens = encoded_frames[0][0].transpose(2, 1).cpu().numpy()

    # tokenize text
    phonemes, langs = text_tokenizer.tokenize(text_pr)
    text_tokens, enroll_x_lens = text_collater(
        [
            phonemes
        ]
    )

    return audio_tokens, text_tokens, langs, text_pr
    
def create_dataset(data_dir, dataloader_process_only, max_duration=120, max_size=20):
    if dataloader_process_only:
        h5_output_path=f"{data_dir}/audio_sum.hdf5"
        ann_output_path=f"{data_dir}/audio_ann_sum.txt"
        #audio_folder = os.path.join(data_dir, 'audio')
        audio_paths = glob.glob(f"{data_dir}/*.wav")  # Change this to match your audio file extension

        # Create or open an HDF5 file
        with h5py.File(h5_output_path, 'w') as h5_file:
            # Loop through each audio and text file, assuming they have the same stem
            for audio_path in audio_paths:
                stem = os.path.splitext(os.path.basename(audio_path))[0]
                audio_tokens, text_tokens, langs, text = make_prompts(name=stem, audio_prompt_path=audio_path)
                
                text_tokens = text_tokens.squeeze(0)
                # Create a group for each stem
                grp = h5_file.create_group(stem)
                # Add audio and text tokens as datasets to the group
                grp.create_dataset('audio', data=audio_tokens)
                #grp.create_dataset('text', data=text_tokens)
                
                with open(ann_output_path, 'a', encoding='utf-8') as ann_file:
                    try:
                        audio, sample_rate = sf.read(audio_path)
                        duration = len(audio) / sample_rate
                        ann_file.write(f'{stem}|{duration}|{langs[0]}|{text}\n')  # 改行を追加
                        print(f"Successfully wrote to {ann_output_path}")
                    except Exception as e:
                        print(f"An error occurred: {e}")
    else:
        dataloader = create_dataloader(data_dir=data_dir, max_duration=max_duration, max_size=max_size)
        return dataloader

def create_dataset_ljspeech(dir_to_txt, dataloader_process_only):
    if dataloader_process_only:
        h5_output_path=f"{os.path.dirname(dir_to_txt)}/audio_sum.hdf5"
        ann_output_path=f"{os.path.dirname(dir_to_txt)}/audio_ann_sum.txt"
        #audio_folder = os.path.join(data_dir, 'audio')
        with open(dir_to_txt, "r", encoding="utf8") as file:
            wavs_txt = file.readlines()

        # Create or open an HDF5 file
        with h5py.File(h5_output_path, 'w') as h5_file:
            # Loop through each audio and text file, assuming they have the same stem
            for speech in wavs_txt:
                speech = speech.replace("\n", "").split("|")
                print(speech)
                audio_path = os.path.join(os.path.dirname(dir_to_txt), speech[0])
                stem = os.path.splitext(os.path.basename(audio_path))[0]
                audio_tokens, text_tokens, langs, text = make_prompts(name=stem, audio_prompt_path=audio_path, transcript=speech[1], cleaner="cje_cleaners")
                
                text_tokens = text_tokens.squeeze(0)
                # Create a group for each stem
                grp = h5_file.create_group(stem)
                # Add audio and text tokens as datasets to the group
                grp.create_dataset('audio', data=audio_tokens)
                #grp.create_dataset('text', data=text_tokens)
                
                with open(ann_output_path, 'a', encoding='utf-8') as ann_file:
                    try:
                        audio, sample_rate = sf.read(audio_path)
                        duration = len(audio) / sample_rate
                        ann_file.write(f'{stem}|{duration}|{langs[0]}|{text}\n')  # 改行を追加
                        print(f"Successfully wrote to {ann_output_path}")
                    except Exception as e:
                        print(f"An error occurred: {e}")
    else:
        dataloader = create_dataloader(data_dir=os.path.dirname(dir_to_txt))
        return dataloader
