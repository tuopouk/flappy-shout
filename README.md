# PLOPLY BIRD! 🐦🗣️

![SHOUT to Survive!](assets/logo.png)

A voice-controlled Flappy Bird clone built entirely in Python using [Dash](https://dash.plotly.com/).

Instead of clicking a mouse or pressing a spacebar, you **SHOUT** into your microphone to make the bird flap its wings! This project demonstrates how to build zero-latency, voice-controlled web applications using Python and the `dash-audio-recorder` component.

## 🚀 Features
- **Zero-latency voice control:** Reads raw volume levels (0-128) directly from the browser's AudioContext.
- **Custom Physics Engine:** Features gravity, jump cooldowns, terminal velocity, and dynamic rotation.
- **Pure Python:** The entire game logic and UI rendering is handled via Dash callbacks.

## 🛠️ Installation

1. Clone this repository:
```bash
git clone [https://github.com/tuopouk/flappy-shout.git](https://github.com/tuopouk/flappy-shout.git)
cd flappy-shout
```

2. Install the required packages (it uses the custom `dash-audio-recorder` component):
```bash
pip install -r requirements.txt
```

3. Run the game:
```bash
python app.py
```

4. Open your browser and go to `http://127.0.0.1:8050/`

## 🎮 How to Play
1. Allow microphone access in your browser and click the small **Mic icon**.
2. Click **Start Game**.
3. **Say "PAH!" or shout** to make the bird jump! Control your volume to navigate through the green pipes.

## 🧠 Powered By
This game was created to showcase the capabilities of the [dash-audio-recorder](https://pypi.org/project/dash-audio-recorder/) package.