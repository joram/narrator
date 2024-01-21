
setup:
	python3 -m pip install virtualenv
	python3 -m virtualenv venv
	source venv/bin/activate
	sudo apt-get install libasound2-dev
	pip install -r requirements.txt


merge_mp3:
	cd frames; rm output_MP3WRAP.mp3
	cd frames; find . -maxdepth 1 -iname '*.mp3' -print0 | sort -z | xargs -0 mp3wrap output.mp3


add_audio_to_video:
	ffmpeg -i /home/john/Downloads/My_Edit_5.mp4 -i ./frames/output_MP3WRAP.mp3 -c:v copy -shortest -map 0:v -map 1:a -y output.mp4

get_frames:
	echo "Enter the video path like: `make get_frames video=/home/john/Downloads/My_Edit_5.mp4`"
	./capture.py $(video)

narrate_frames:
	./narrate.py

make_a_documentary:
	./capture.py

read_metadata:
	#ffprobe -v quiet -print_format json -show_format -show_streams /home/john/Downloads/My_Edit_5.mp4 > metadata.json
	ffmpeg -i /home/john/Downloads/My_Edit_5.mp4 -f ffmetadata metadata.txt