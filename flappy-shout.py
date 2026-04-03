import os
import dash_audio_recorder
from dash import Dash, html, dcc, Input, Output, State, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import time
import random

# ==========================================
# 1. ENVIRONMENT DETECTION (Local vs. Cloud)
# ==========================================
# Heroku automatically sets a 'PORT' environment variable. 
# If it's missing, we know the game is running locally on your computer.
IS_LOCAL = os.environ.get('PORT') is None

if IS_LOCAL:
    # 🏎️ LOCAL SETTINGS: Ultra-smooth 25 FPS (No network lag)
    TICK_RATE = 40
    CSS_TRANSITION = '0.04s linear'
    GRAVITY = 1.5         
    JUMP_STRENGTH = -12   
    PIPE_SPEED = 10       
    JUMP_COOLDOWN = 0.2
else:
    # ☁️ CLOUD SETTINGS: Stable 6.6 FPS (Prevents Heroku/Mobile network jams)
    TICK_RATE = 150
    CSS_TRANSITION = '0.15s linear'
    GRAVITY = 4.0         
    JUMP_STRENGTH = -22   
    PIPE_SPEED = 20       
    JUMP_COOLDOWN = 0.4

HOLE_SIZE = 170       
SHOUT_THRESHOLD = 40  

# ==========================================
# 2. APP INITIALIZATION
# ==========================================
app = Dash(__name__, 
           external_stylesheets=[dbc.themes.BOOTSTRAP],
           suppress_callback_exceptions=True, 
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"}])

server = app.server 

# ==========================================
# 3. APP LAYOUT
# ==========================================
app.layout = dbc.Container([
    
    dbc.Row([
        dbc.Col([
            html.H1("Ploply Bird 🐦🗣️", className="text-center mt-3 mb-1"),
            # Shows a small indicator of which version is running
            html.P(f"SHOUT to survive! (Mode: {'Local Smooth' if IS_LOCAL else 'Cloud Stable'})", 
                   className="text-center fw-bold mb-3 text-muted"),
        ])
    ]),

    dbc.Row(className="justify-content-center align-items-center mb-3", children=[
        dbc.Col(width="auto", children=[
            dash_audio_recorder.DashAudioRecorder(
                id='recorder', visualMode='small', recordMode='click', streamMode=True,
                echoCancellation=False, noiseSuppression=False, autoGainControl=False
            )
        ]),
        dbc.Col(width="auto", children=[
            dbc.Button("▶ START", id='start-btn', n_clicks=0, color="success", size="lg", className="fw-bold shadow-sm")
        ]),
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

    # The interval now dynamically uses TICK_RATE based on the environment!
    dcc.Interval(id='game-clock', interval=TICK_RATE, n_intervals=0, disabled=True),
    
    dcc.Store(id='game-state', data={
        'bird_y': 200, 'velocity': 0, 'pipe_x': 400, 'pipe_hole_y': 150, 
        'score': 0, 'status': 'waiting', 'start_clicks': 0, 'processed_jump': 0 
    }),
    
    dcc.Store(id='last-jump-time', data=0)

], fluid=True, className="pb-5")

# ==========================================
# 4. CALLBACK: VOLUME METER
# ==========================================
@app.callback(
    Output('meter-fill', 'style'),
    Input('recorder', 'currentVolume')
)
def update_volume_meter(volume):
    if volume is None: return {'width': '0%', 'height': '100%', 'backgroundColor': '#198754'}
    pct = min(100, (volume / 128) * 100)
    color = '#dc3545' if volume > SHOUT_THRESHOLD else '#198754'
    return {'width': f'{pct}%', 'height': '100%', 'backgroundColor': color, 'transition': 'width 0.1s ease'}

# ==========================================
# 5. CALLBACK: CLIENTSIDE VOICE DETECTION
# ==========================================
app.clientside_callback(
    """
    function(volume, last_time) {
        if (!volume || volume < 40) return window.dash_clientside.no_update; 
        return Date.now() / 1000.0; 
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
    Output('game-clock', 'disabled'), 
    Input('game-clock', 'n_intervals'), 
    Input('start-btn', 'n_clicks'),     
    State('game-state', 'data'),
    State('last-jump-time', 'data')
)
def update_game(n, start_clicks, state, last_jump):
    if start_clicks is None: start_clicks = 0

    if start_clicks > state.get('start_clicks', 0):
        state = {
            'bird_y': 200, 'velocity': -15, 'pipe_x': 400, 
            'pipe_hole_y': random.randint(50, 170), 'score': 0, 
            'status': 'playing', 'start_clicks': start_clicks,
            'processed_jump': time.time() 
        }

    if state['status'] == 'waiting':
        screen = html.H2("Ready?", className="text-center text-dark", style={'marginTop': '150px'})
        return state, screen, "Press START!", True 

    if state['status'] == 'game_over':
        screen = html.H1("GAME OVER!", className="text-center text-danger fw-bold", style={'marginTop': '100px'})
        return state, screen, f"Score: {state['score']} 🏆", True 

    # --- PHYSICS ENGINE ---
    now = time.time()
    
    # Dynamics cooldown based on environment
    if (now - last_jump < JUMP_COOLDOWN) and (now - state.get('processed_jump', 0) > JUMP_COOLDOWN):
        state['velocity'] = JUMP_STRENGTH
        state['processed_jump'] = now 
        
    state['velocity'] += GRAVITY
    
    # Cap falling speed dynamically
    max_fall = 20 if IS_LOCAL else 30
    if state['velocity'] > max_fall: state['velocity'] = max_fall
        
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
    # Dynamics rotation based on environment
    rot_multiplier = 4 if IS_LOCAL else 2.5
    rotation = max(-20, min(90, state['velocity'] * rot_multiplier))
    
    
    
    pipe_top = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': '0px', 
        'width': f'{pipe_width}px', 'height': f"{state['pipe_hole_y']}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 
        'transition': f'left {CSS_TRANSITION}'
    })
    bird = html.Div(
        "🐦", 
        style={
            'position': 'absolute', 
            'left': f'{bird_x}px', 
            'top': f"{state['bird_y']}px", 
            'width': f'{bird_size}px', 
            'height': f'{bird_size}px', 
            
            # --- EMOJIN SETTINGS ---
            'fontSize': '26px',              # Emoji size
            'textAlign': 'center',           
            'lineHeight': f'{bird_size}px',  
            
            
            'transform': f'rotate({rotation}deg)', 
            'transition': f'top {CSS_TRANSITION}, transform 0.1s ease'
        }
    )
    pipe_bottom = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': f"{state['pipe_hole_y'] + HOLE_SIZE}px", 
        'width': f'{pipe_width}px', 'height': f"{400 - (state['pipe_hole_y'] + HOLE_SIZE)}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 
        'transition': f'left {CSS_TRANSITION}'
    })

    return state, [bird, pipe_top, pipe_bottom], f"Score: {state['score']}", False

if __name__ == '__main__':
    app.run(debug=True)
