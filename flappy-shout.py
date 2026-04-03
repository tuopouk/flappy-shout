import dash_audio_recorder
from dash import Dash, html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import time
import random

# ==========================================
# 1. APP INITIALIZATION & BOOTSTRAP THEME
# ==========================================
# Using Dash Bootstrap Components (DBC) for a responsive, mobile-first layout.
# The viewport meta tag prevents the browser from zooming out on mobile devices.
app = Dash(__name__, 
           external_stylesheets=[dbc.themes.BOOTSTRAP],
           suppress_callback_exceptions=True, 
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"}])

server = app.server # Expose the Flask server for Heroku's Gunicorn

# ==========================================
# 2. GAME SETTINGS
# ==========================================
# Physics are tuned for a 150ms game loop interval (~6.6 FPS server-side).
GRAVITY = 4.5         # Downward acceleration per frame
JUMP_STRENGTH = -25   # Upward velocity applied when a shout is detected
PIPE_SPEED = 25       # Horizontal movement speed of the pipes
HOLE_SIZE = 180       # Vertical gap space between top and bottom pipes
SHOUT_THRESHOLD = 40  # Volume threshold (0-128). Note: Also hardcoded in the JS callback below!

# ==========================================
# 3. APP LAYOUT (Bootstrap Grid System)
# ==========================================
app.layout = dbc.Container([
    
    # --- HEADER SECTION ---
    dbc.Row([
        dbc.Col([
            html.H1("Flappy Shout! 🐦🗣️", className="text-center mt-3 mb-1"),
            html.P("1. Allow Mic 👉 2. Start Game 👉 3. SHOUT!", className="text-center fw-bold mb-3 text-muted"),
        ])
    ]),

    # --- CONTROLS SECTION ---
    dbc.Row(className="justify-content-center align-items-center mb-3", children=[
        
        # 1. Microphone Widget
        dbc.Col(width="auto", children=[
            dash_audio_recorder.DashAudioRecorder(
                id='recorder',
                visualMode='small',
                recordMode='click',
                streamMode=True,
                echoCancellation=False, noiseSuppression=False, autoGainControl=False
            )
        ]),
        
        # 2. Start Button
        dbc.Col(width="auto", children=[
            dbc.Button("▶ START", id='start-btn', n_clicks=0, color="success", size="lg", className="fw-bold shadow-sm")
        ]),

        # 3. Volume Meter
        dbc.Col(width="auto", children=[
            html.Div([
                html.Div("Mic Level", className="text-center text-muted fw-bold", style={'fontSize': '10px', 'marginBottom': '2px'}),
                html.Div(id='meter-bg', style={
                    'width': '80px', 'height': '15px', 'backgroundColor': '#e9ecef',
                    'borderRadius': '5px', 'overflow': 'hidden', 'border': '1px solid #ced4da'
                }, children=[
                    html.Div(id='meter-fill', style={
                        'width': '0%', 'height': '100%', 'backgroundColor': '#198754',
                        'transition': 'width 0.1s ease'
                    })
                ])
            ])
        ])
    ]),

    # --- GAME BOARD SECTION ---
    dbc.Row(className="justify-content-center", children=[
        dbc.Col(width="auto", children=[
            html.Div(id='game-board', className="shadow-lg", style={
                'width': '350px', 'height': '400px', 'backgroundColor': '#87CEEB', 
                'position': 'relative', 'overflow': 'hidden',
                'border': '4px solid #212529', 'borderRadius': '10px'
            }),
            html.H2(id='score-display', className="text-center mt-3 fw-bold")
        ])
    ]),

    # --- INVISIBLE GAME COMPONENTS ---
    # The clock ticks every 150ms. Fast enough to be responsive, slow enough to avoid network jams.
    dcc.Interval(id='game-clock', interval=150, n_intervals=0),
    
    # Memory store for game physics and state
    dcc.Store(id='game-state', data={
        'bird_y': 200, 'velocity': 0, 
        'pipe_x': 400, 'pipe_hole_y': 150, 
        'score': 0, 'status': 'waiting',
        'start_clicks': 0,
        'processed_jump': 0 
    }),
    
    # Memory store for the exact timestamp of the last detected shout
    dcc.Store(id='last-jump-time', data=0)

], fluid=True, className="pb-5")

# ==========================================
# 4. CALLBACK: VOLUME METER UI UPDATE
# ==========================================
@app.callback(
    Output('meter-fill', 'style'),
    Input('recorder', 'currentVolume')
)
def update_volume_meter(volume):
    if volume is None:
        return {'width': '0%', 'height': '100%', 'backgroundColor': '#198754'}
    
    pct = min(100, (volume / 128) * 100)
    color = '#dc3545' if volume > SHOUT_THRESHOLD else '#198754' # Red if shouting, Green if quiet
    
    return {
        'width': f'{pct}%', 
        'height': '100%', 
        'backgroundColor': color,
        'transition': 'width 0.1s ease'
    }

# ==========================================
# 5. CALLBACK: VOICE DETECTION (CLIENTSIDE)
# ==========================================
# PERFORMANCE MAGIC: This JavaScript code runs entirely in the user's browser.
# Instead of sending every microphone volume update to the Heroku server (causing lag),
# the browser listens locally and only updates the 'last-jump-time' when a shout occurs.
app.clientside_callback(
    """
    function(volume, last_time) {
        if (volume === null) {
            return window.dash_clientside.no_update;
        }
        
        // If volume exceeds threshold (40), return the current exact time in seconds
        if (volume > 40) {
            return Date.now() / 1000.0; 
        }
        
        // Prevent unnecessary network traffic
        return window.dash_clientside.no_update; 
    }
    """,
    Output('last-jump-time', 'data'),
    Input('recorder', 'currentVolume'),
    State('last-jump-time', 'data')
)

# ==========================================
# 6. CALLBACK: MAIN GAME ENGINE
# ==========================================
@app.callback(
    Output('game-state', 'data'),
    Output('game-board', 'children'),
    Output('score-display', 'children'),
    Input('game-clock', 'n_intervals'), 
    Input('start-btn', 'n_clicks'),     
    State('game-state', 'data'),
    State('last-jump-time', 'data')
)
def update_game(n, start_clicks, state, last_jump):
    
    if start_clicks is None:
        start_clicks = 0

    # START GAME INITIALIZATION
    if start_clicks > state.get('start_clicks', 0):
        state = {
            'bird_y': 200, 'velocity': -15, 'pipe_x': 400, 
            'pipe_hole_y': random.randint(50, 170), 'score': 0, 
            'status': 'playing', 'start_clicks': start_clicks,
            'processed_jump': time.time() 
        }

    # UI: WAITING STATE
    if state['status'] == 'waiting':
        return state, html.H2("Ready?", className="text-center text-dark", style={'marginTop': '150px'}), "Press START!"

    # UI: GAME OVER STATE
    if state['status'] == 'game_over':
        return state, html.H1("GAME OVER!", className="text-center text-danger fw-bold", style={'marginTop': '100px'}), f"Score: {state['score']} 🏆"

    # --- PHYSICS CALCULATIONS ---
    now = time.time()
    
    # Check if a shout happened recently and enforce a cooldown to prevent double-jumping
    if (now - last_jump < 0.50) and (now - state.get('processed_jump', 0) > 0.6):
        state['velocity'] = JUMP_STRENGTH
        state['processed_jump'] = now 
        
    state['velocity'] += GRAVITY
    
    # Cap maximum falling speed
    if state['velocity'] > 35: 
        state['velocity'] = 35
        
    state['bird_y'] += state['velocity']
    state['pipe_x'] -= PIPE_SPEED
    
    # Recycle pipe when it goes off screen
    if state['pipe_x'] < -50: 
        state['pipe_x'] = 350 
        state['score'] += 1
        state['pipe_hole_y'] = random.randint(50, 170) 

    # --- COLLISION DETECTION ---
    bird_x, bird_size, pipe_width = 50, 30, 50
    
    # 1. Floor & Ceiling Bounds
    if state['bird_y'] > 370 or state['bird_y'] < 0:
        state['status'] = 'game_over'
        
    # 2. Pipe Hitboxes
    if (state['pipe_x'] < bird_x + bird_size) and (state['pipe_x'] + pipe_width > bird_x):
        if state['bird_y'] < state['pipe_hole_y'] or (state['bird_y'] + bird_size) > (state['pipe_hole_y'] + HOLE_SIZE):
            state['status'] = 'game_over'

    # --- RENDERING & CSS ANIMATION TRICKS ---
    rotation = max(-20, min(90, state['velocity'] * 2))
    
    # CSS TRICK: The server updates physics every 150ms. 
    # The 'transition: 0.15s linear' property tells the browser's GPU to smoothly 
    # interpolate the movement in between those server updates, creating a seamless 60fps feel.
    
    bird = html.Div(style={
        'position': 'absolute', 'left': f'{bird_x}px', 'top': f"{state['bird_y']}px", 
        'width': f'{bird_size}px', 'height': f'{bird_size}px', 'backgroundColor': '#FFC107', 
        'borderRadius': '50%', 'border': '2px solid black', 'transform': f'rotate({rotation}deg)', 
        'transition': 'top 0.15s linear, transform 0.1s ease'
    })
    
    pipe_top = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': '0px', 
        'width': f'{pipe_width}px', 'height': f"{state['pipe_hole_y']}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 'transition': 'left 0.15s linear'
    })
    
    pipe_bottom = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': f"{state['pipe_hole_y'] + HOLE_SIZE}px", 
        'width': f'{pipe_width}px', 'height': f"{400 - (state['pipe_hole_y'] + HOLE_SIZE)}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 'transition': 'left 0.15s linear'
    })

    return state, [bird, pipe_top, pipe_bottom], f"Score: {state['score']}"

if __name__ == '__main__':
    app.run(debug=True)
