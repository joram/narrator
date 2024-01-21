#!/usr/bin/env python
import base64
import errno
import os
import time

import cv2
import dotenv
from elevenlabs import generate
from openai import OpenAI

dotenv.load_dotenv()

client = OpenAI()

folder = "frames"
frames_dir = os.path.abspath(os.path.join(os.getcwd(), folder))
os.makedirs(frames_dir, exist_ok=True)


def get_frame(vidcap, sec, filepath):
    vidcap.set(cv2.CAP_PROP_POS_MSEC,sec*1000)
    hasFrames,image = vidcap.read()
    if hasFrames:
        cv2.imwrite(filepath, image)


def parse_description_frames_file(filepath):
    i = 0
    with open(filepath) as f:
        lines = [line.rstrip() for line in f.readlines()]
        # break each line into timestamp,duration,description
        for line in lines:
            double_space = "  "
            while double_space in line:
                line = line.replace(double_space, " ")
            words = line.split(" ")
            timestamp = words[0]
            parts = timestamp.split(":")
            seconds = int(parts[0])*60*60 + int(parts[1])*60 + int(parts[2])
            duration = int(words[1])
            description = " ".join(words[2:])
            yield i, seconds, duration, description
            i += 1


def encode_image(image_path):
    while True:
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except IOError as e:
            if e.errno != errno.EACCES:
                # Not a "file in use" error, re-raise
                raise
            # File is being written to, wait a bit and retry
            time.sleep(0.1)


def generate_new_line(base64_image):
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image"},
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{base64_image}",
                },
            ],
        },
    ]


def adjust_length_to_match(text, target_seconds, script, filepath):
    words = text.split(" ")
    num_words = len(words)
    minutes = num_words/200
    current_seconds = minutes*60
    percentage = int(target_seconds/current_seconds*100)
    prompt = f"shorten the following text to roughly {percentage}% it's original size:\n{text}"

    if os.path.exists(filepath):
        f = open(filepath)
        response_text = f.read()
    else:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ]
            + script,
            max_tokens=500,
        )
        response_text = response.choices[0].message.content
        f = open(filepath, "w")
        f.write(response_text)

    old_word_count = len(text.split(" "))
    new_word_count = len(response_text.split(" "))
    print(f"old word count: {old_word_count}")
    print(f"new word count: {new_word_count}")
    print(f"new text: {response_text}")

    return response_text


def analyze_image(base64_image, filepath, script, description, seconds):
    if os.path.exists(filepath):
        f = open(filepath)
        return f.read()

    prompt = f"""
        You are Sir David Attenborough. Narrate the picture as if it is a video of snow and mountains, with these humans ski touring as if it is a nature documentary.
        Assume this picture is a video, with this section of the video described as \"{description}\".
        Make it snarky and funny. Don't repeat yourself. Make it extremely short and succinct.
        Don't reference the picture directly. If they do anything remotely interesting, make a big deal about it!
    """
    print("Prompt:\n")
    print(prompt)
    print("\n\n")

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
        ]
        + script
        + generate_new_line(base64_image),
        max_tokens=500,
    )
    response_text = response.choices[0].message.content
    f = open(filepath, "w")
    f.write(response_text)
    return response_text


def make_audio(text, filepath_wave, filepath_mp3):
    if "frame_0" in filepath_wave:
        return
    if os.path.exists(filepath_mp3):
        return
    audio = generate(
        text,
        api_key=os.environ.get("ELEVENLABS_API_KEY"),
        voice=os.environ.get("ELEVENLABS_VOICE_ID"),
    )
    with open(filepath_wave, "wb") as f:
        f.write(audio)
    os.system(f"ffmpeg -i \"{filepath_wave}\" \"{filepath_mp3}\"")


def narrate_video(video_filepath, description_frames):
    # Initialize the webcam
    script = []
    vidcap = cv2.VideoCapture(video_filepath)
    for i, seconds, duration, description in parse_description_frames_file(description_frames):
        description_s = description.replace(" ", "_").replace(".", "")
        image_filepath = os.path.join(frames_dir, os.path.join(frames_dir, f"frame_{i} {description_s}.jpg"))
        print(f"{i} \t {image_filepath}")
        get_frame(vidcap, seconds, image_filepath)
        narration = analyze_image(
            base64_image=encode_image(image_filepath),
            filepath=image_filepath.replace(".jpg", ".txt"),
            script=script,
            description=description,
            seconds=duration,
        )

        adjusted_narration = adjust_length_to_match(
            text=narration,
            target_seconds=duration,
            script=script,
            filepath=image_filepath.replace(".jpg", ".adjusted.txt"),
        )
        make_audio(
            text=adjusted_narration,
            filepath_wave=image_filepath.replace(".jpg", ".wav"),
            filepath_mp3=image_filepath.replace(".jpg", ".mp3"),
        )

        script = script + [{"role": "assistant", "content": narration}]

    vidcap.release()
    cv2.destroyAllWindows()

def line_wrap(text):
    import textwrap
    return textwrap.fill(text, 80)

def join_narration_files_into_a_single_transcript_file():
    import os
    import glob
    import re

    # Get all the narration files
    narration_files = glob.glob("./frames/*.adjusted.txt")
    narration_files.sort(key=lambda f: int(re.sub('\D', '', f)))

    # Join all the narration files into a single transcript file
    with open("./frames/full_transcript.txt", "w") as outfile:
        for narration_file in narration_files:
            with open(narration_file) as infile:
                outfile.write(f"###### {narration_file} #######\n")
                chapter = line_wrap(infile.read())
                outfile.write(chapter)
                outfile.write("\n\n\n")



narrate_video(
    "./original_video.mp4",
    "./description_frames.txt",
)
join_narration_files_into_a_single_transcript_file()