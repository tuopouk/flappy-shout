import dash_audio_recorder
from dash import Dash, html, dcc, Input, Output, State, ctx
import time
import random

# ==========================================
# 1. APP INITIALIZATION & MOBILE SCALING
# ==========================================
# CRITICAL: The viewport meta tag prevents mobile browsers from zooming out,
# forcing the game to scale correctly on smartphone screens.
app = Dash(__name__, suppress_callback_exceptions=True, meta_tags=[
    {"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"}
])
server = app.server # Expose the Flask server for Heroku's Gunicorn

# ==========================================
# 2. GAME SETTINGS (Ultra-Stable Cloud Version)
# ==========================================
# To prevent mobile networks from crashing due to too many requests, 
# the game updates every 250ms (4 FPS). The physics are scaled up accordingly.
GRAVITY = 4.5         # Stronger gravity per frame
JUMP_STRENGTH = -25   # Stronger jump impulse
PIPE_SPEED = 25       # Pipes move in larger increments
HOLE_SIZE = 180       # The vertical gap space between top and bottom pipes
SHOUT_THRESHOLD = 40  # Minimum microphone volume (0-128) to trigger a jump

# ==========================================
# 3. APP LAYOUT & UI
# ==========================================
app.layout = html.Div([
    html.H1("Flappy Shout! 🐦🗣️", style={'textAlign': 'center', 'fontSize': '24px'}),
    html.P("1. Allow Mic 👉 2. Start Game 👉 3. SHOUT!", style={'textAlign': 'center', 'fontWeight': 'bold', 'fontSize': '14px'}),
    
    # UI Controls
    html.Div([
        dash_audio_recorder.DashAudioRecorder(
            id='recorder',
            visualMode='small',
            recordMode='click',
            streamMode=True,
            echoCancellation=False, noiseSuppression=False, autoGainControl=False
        ),
        html.Button("▶ START", id='start-btn', n_clicks=0, style={
            'fontSize': '16px', 'padding': '10px 20px', 'backgroundColor': '#4CAF50', 
            'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer',
            'marginLeft': '10px', 'verticalAlign': 'top'
        })
    ], style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'marginBottom': '10px'}),

    # Game Canvas / Board
    html.Div([
        # WIDTH REDUCED TO 350px: Ensures the board fits on narrow smartphone screens
        html.Div(id='game-board', style={
            'width': '350px', 'height': '400px', 'backgroundColor': '#87CEEB', 
            'position': 'relative', 'overflow': 'hidden', 'margin': '0 auto',
            'border': '4px solid #333', 'borderRadius': '10px'
        }),
        html.H2(id='score-display', style={'textAlign': 'center'})
    ]),

    # GAME CLOCK: 250ms interval (4 FPS). 
    # This prevents the mobile network connection from bottlenecking,
    # ensuring the "blue screen of death" doesn't occur on cellular data.
    dcc.Interval(id='game-clock', interval=250, n_intervals=0),
    
    # GAME STATE MEMORY
    dcc.Store(id='game-state', data={
        'bird_y': 200, 'velocity': 0, 
        'pipe_x': 400, 'pipe_hole_y': 150, 
        'score': 0, 'status': 'waiting',
        'start_clicks': 0,
        'processed_jump': 0 
    }),
    
    # Stores the timestamp of the last loud noise
    dcc.Store(id='last-jump-time', data=0)
])

# ==========================================
# 4. CALLBACK: MICROPHONE LISTENER
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
# 5. CALLBACK: GAME ENGINE & PHYSICS
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
            'bird_y': 200, 
            'velocity': -15, 
            'pipe_x': 400, 
            'pipe_hole_y': random.randint(50, 170), 
            'score': 0, 
            'status': 'playing',
            'start_clicks': start_clicks,
            'processed_jump': time.time() 
        }

    # UI: WAITING STATE
    if state['status'] == 'waiting':
        screen = html.Div([
            html.H2("Ready?", style={'marginTop': '150px', 'textAlign': 'center', 'color': '#333'})
        ])
        return state, screen, "Press START to begin!"

    # UI: GAME OVER STATE
    if state['status'] == 'game_over':
        game_over_screen = html.Div([
            html.H1("GAME OVER!", style={'color': 'red', 'marginTop': '100px', 'textAlign': 'center'}),
            html.P("Press START to try again", style={'textAlign': 'center'})
        ])
        return state, game_over_screen, f"Score: {state['score']} 🏆"

    # --- PHYSICS CALCULATIONS ---
    now = time.time()
    
    # JUMP WINDOW: Widened to compensate for mobile network latency
    if (now - last_jump < 0.50) and (now - state.get('processed_jump', 0) > 0.6):
        state['velocity'] = JUMP_STRENGTH
        state['processed_jump'] = now 
        
    state['velocity'] += GRAVITY
    
    # TERMINAL VELOCITY: Cap maximum falling speed
    if state['velocity'] > 35:
        state['velocity'] = 35
        
    state['bird_y'] += state['velocity']

    # MOVE PIPES
    state['pipe_x'] -= PIPE_SPEED
    if state['pipe_x'] < -50: 
        state['pipe_x'] = 350 
        state['score'] += 1
        state['pipe_hole_y'] = random.randint(50, 170) 

    # --- COLLISION DETECTION ---
    bird_x = 50
    bird_size = 30
    pipe_width = 50
    
    # 1. Floor & Ceiling
    if state['bird_y'] > 370 or state['bird_y'] < 0:
        state['status'] = 'game_over'

    # 2. Pipes
    if (state['pipe_x'] < bird_x + bird_size) and (state['pipe_x'] + pipe_width > bird_x):
        if state['bird_y'] < state['pipe_hole_y'] or (state['bird_y'] + bird_size) > (state['pipe_hole_y'] + HOLE_SIZE):
            state['status'] = 'game_over'

    # ==========================================
    # 6. RENDERING & CSS ANIMATION TRICKS
    # ==========================================
    
    rotation = max(-20, min(90, state['velocity'] * 2))

    # CSS TRICK: The server updates only every 250ms to save bandwidth.
    # However, the 'transition: 0.25s linear' property commands the browser's GPU 
    # to smoothly interpolate the movement between frames. This bridges the gap 
    # and makes the game look surprisingly smooth on the client side!
    
    bird = html.Div(style={
        'position': 'absolute', 'left': f'{bird_x}px', 'top': f"{state['bird_y']}px", 
        'width': f'{bird_size}px', 'height': f'{bird_size}px', 
        'backgroundColor': '#FFD700', 'borderRadius': '50%', 'border': '2px solid black',
        'transform': f'rotate({rotation}deg)', 
        'transition': 'top 0.25s linear, transform 0.2s ease', # 250ms smooth interpolation
        'boxShadow': 'inset -3px -3px 0px 0px rgba(0,0,0,0.2)'  
    })
    
    pipe_top = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': '0px', 
        'width': f'{pipe_width}px', 'height': f"{state['pipe_hole_y']}px", 
        'backgroundColor': '#2E8B57', 'border': '3px solid #006400',
        'transition': 'left 0.25s linear' # 250ms smooth interpolation
    })
    
    pipe_bottom = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': f"{state['pipe_hole_y'] + HOLE_SIZE}px", 
        'width': f'{pipe_width}px', 'height': f"{400 - (state['pipe_hole_y'] + HOLE_SIZE)}px", 
        'backgroundColor': '#2E8B57', 'border': '3px solid #006400',
        'transition': 'left 0.25s linear' # 250ms smooth interpolation
    })

    return state, [bird, pipe_top, pipe_bottom], f"Score: {state['score']}"

if __name__ == '__main__':
    app.run(debug=True)
