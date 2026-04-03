import dash_audio_recorder
from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import time
import random

# ==========================================
# 1. APP INITIALIZATION & BOOTSTRAP THEME
# ==========================================
# Added a Bootstrap stylesheet for clean, mobile-responsive styling.
# The meta_tags ensure the browser doesn't try to zoom out on mobile.
app = Dash(__name__, 
           external_stylesheets=[dbc.themes.BOOTSTRAP],
           suppress_callback_exceptions=True, 
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"}])

server = app.server 

# ==========================================
# 2. GAME SETTINGS (Optimized for Mobile/Cloud)
# ==========================================
GRAVITY = 4.5         
JUMP_STRENGTH = -25   
PIPE_SPEED = 25       
HOLE_SIZE = 180       
SHOUT_THRESHOLD = 40  # Adjust based on the volume meter!

# ==========================================
# 3. APP LAYOUT (Bootstrap Grid System)
# ==========================================
# Using dbc.Container allows the layout to adapt to the screen size automatically.
app.layout = dbc.Container([
    
    # --- HEADER SECTION ---
    dbc.Row([
        dbc.Col([
            html.H1("Flappy Shout! 🐦🗣️", className="text-center mt-3 mb-1"),
            html.P("1. Allow Mic 👉 2. Start Game 👉 3. SHOUT!", className="text-center fw-bold mb-3 text-muted"),
        ])
    ]),

    # --- CONTROLS SECTION ---
    # Centered row for the microphone, start button, and volume meter
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
        
        # 2. Start Button (Now a Bootstrap styled button)
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
                        'width': '0%', 'height': '100%', 'backgroundColor': '#198754', # Bootstrap success green
                        'transition': 'width 0.1s ease'
                    })
                ])
            ])
        ])
        
    ]),

    # --- GAME BOARD SECTION ---
    dbc.Row(className="justify-content-center", children=[
        dbc.Col(width="auto", children=[
            # The game board maintains strict pixel dimensions internally for the physics to work
            html.Div(id='game-board', className="shadow-lg", style={
                'width': '350px', 'height': '400px', 'backgroundColor': '#87CEEB', 
                'position': 'relative', 'overflow': 'hidden',
                'border': '4px solid #212529', 'borderRadius': '10px'
            }),
            html.H2(id='score-display', className="text-center mt-3 fw-bold")
        ])
    ]),

    # --- INVISIBLE GAME COMPONENTS ---
    dcc.Interval(id='game-clock', interval=250, n_intervals=0),
    
    dcc.Store(id='game-state', data={
        'bird_y': 200, 'velocity': 0, 
        'pipe_x': 400, 'pipe_hole_y': 150, 
        'score': 0, 'status': 'waiting',
        'start_clicks': 0,
        'processed_jump': 0 
    }),
    
    dcc.Store(id='last-jump-time', data=0)

], fluid=True, className="pb-5") # fluid=True ensures it spans correctly on mobile

# ==========================================
# 4. CALLBACK: VOLUME METER UPDATE
# ==========================================
@app.callback(
    Output('meter-fill', 'style'),
    Input('recorder', 'currentVolume')
)
def update_volume_meter(volume):
    if volume is None:
        return {'width': '0%', 'height': '100%', 'backgroundColor': '#198754'}
    
    pct = min(100, (volume / 128) * 100)
    color = '#dc3545' if volume > SHOUT_THRESHOLD else '#198754' # Bootstrap danger/success colors
    
    return {
        'width': f'{pct}%', 
        'height': '100%', 
        'backgroundColor': color,
        'transition': 'width 0.1s ease'
    }

# ==========================================
# 5. CALLBACK: VOICE DETECTION
# ==========================================
@app.callback(
    Output('last-jump-time', 'data'),
    Input('recorder', 'currentVolume'),
    State('last-jump-time', 'data')
)
def detect_shout(volume, last_time):
    if volume is None:
        return last_time
        
    if volume > SHOUT_THRESHOLD:
        return time.time()
        
    return last_time

# ==========================================
# 6. CALLBACK: GAME ENGINE
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

    if start_clicks > state.get('start_clicks', 0):
        state = {
            'bird_y': 200, 'velocity': -15, 'pipe_x': 400, 
            'pipe_hole_y': random.randint(50, 170), 'score': 0, 
            'status': 'playing', 'start_clicks': start_clicks,
            'processed_jump': time.time() 
        }

    # Used Bootstrap text utility classes (e.g., text-dark, text-danger)
    if state['status'] == 'waiting':
        return state, html.H2("Ready?", className="text-center text-dark", style={'marginTop': '150px'}), "Press START!"

    if state['status'] == 'game_over':
        return state, html.H1("GAME OVER!", className="text-center text-danger fw-bold", style={'marginTop': '100px'}), f"Score: {state['score']} 🏆"

    # --- PHYSICS ---
    now = time.time()
    if (now - last_jump < 0.50) and (now - state.get('processed_jump', 0) > 0.6):
        state['velocity'] = JUMP_STRENGTH
        state['processed_jump'] = now 
        
    state['velocity'] += GRAVITY
    if state['velocity'] > 35: state['velocity'] = 35
    state['bird_y'] += state['velocity']
    state['pipe_x'] -= PIPE_SPEED
    
    if state['pipe_x'] < -50: 
        state['pipe_x'] = 350 
        state['score'] += 1
        state['pipe_hole_y'] = random.randint(50, 170) 

    # --- COLLISIONS ---
    bird_x, bird_size, pipe_width = 50, 30, 50
    if state['bird_y'] > 370 or state['bird_y'] < 0:
        state['status'] = 'game_over'
    if (state['pipe_x'] < bird_x + bird_size) and (state['pipe_x'] + pipe_width > bird_x):
        if state['bird_y'] < state['pipe_hole_y'] or (state['bird_y'] + bird_size) > (state['pipe_hole_y'] + HOLE_SIZE):
            state['status'] = 'game_over'

    # --- RENDERING ---
    rotation = max(-20, min(90, state['velocity'] * 2))
    
    bird = html.Div(style={
        'position': 'absolute', 'left': f'{bird_x}px', 'top': f"{state['bird_y']}px", 
        'width': f'{bird_size}px', 'height': f'{bird_size}px', 'backgroundColor': '#FFC107', # Bootstrap warning yellow
        'borderRadius': '50%', 'border': '2px solid black', 'transform': f'rotate({rotation}deg)', 
        'transition': 'top 0.25s linear, transform 0.2s ease'
    })
    
    pipe_top = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': '0px', 
        'width': f'{pipe_width}px', 'height': f"{state['pipe_hole_y']}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 'transition': 'left 0.25s linear'
    })
    
    pipe_bottom = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': f"{state['pipe_hole_y'] + HOLE_SIZE}px", 
        'width': f'{pipe_width}px', 'height': f"{400 - (state['pipe_hole_y'] + HOLE_SIZE)}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 'transition': 'left 0.25s linear'
    })

    return state, [bird, pipe_top, pipe_bottom], f"Score: {state['score']}"

if __name__ == '__main__':
    app.run(debug=True)
