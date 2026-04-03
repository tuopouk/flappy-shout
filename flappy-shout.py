import dash_audio_recorder
from dash import Dash, html, dcc, Input, Output, State, ctx
import time
import random

app = Dash(__name__, suppress_callback_exceptions=True)

# ==========================================
# 1. GAME SETTINGS & PHYSICS CONFIGURATION
# ==========================================
GRAVITY = 0.7         # Downward acceleration applied every frame
JUMP_STRENGTH = -7.5  # Upward velocity applied when a shout is detected
PIPE_SPEED = 4        # Horizontal speed of the moving pipes
HOLE_SIZE = 180       # The vertical gap space between top and bottom pipes
SHOUT_THRESHOLD = 40  # Minimum volume level (0-128) required to trigger a jump

# ==========================================
# 2. APP LAYOUT & USER INTERFACE
# ==========================================
app.layout = html.Div([
    html.H1("Flappy Shout! 🐦🗣️", style={'textAlign': 'center'}),
    html.P("1. Click the Mic  👉  2. Click Start Game  👉  3. SHOUT to fly!", 
           style={'textAlign': 'center', 'fontWeight': 'bold'}),
    
    # UI Controls: Microphone component and Start Button
    html.Div([
        dash_audio_recorder.DashAudioRecorder(
            id='recorder',
            visualMode='small',
            recordMode='click',
            streamMode=True, # Enables continuous live audio processing
            echoCancellation=False, noiseSuppression=False, autoGainControl=False
        ),
        html.Button("▶ START GAME", id='start-btn', n_clicks=0, style={
            'fontSize': '18px', 'padding': '15px 30px', 'backgroundColor': '#4CAF50', 
            'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer',
            'marginLeft': '20px', 'verticalAlign': 'top'
        })
    ], style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'marginBottom': '20px'}),

    # Game Canvas / Board
    html.Div([
        html.Div(id='game-board', style={
            'width': '400px', 'height': '400px', 'backgroundColor': '#87CEEB', # Sky blue background
            'position': 'relative', 'overflow': 'hidden', 'margin': '0 auto',
            'border': '4px solid #333', 'borderRadius': '10px'
        }),
        html.H2(id='score-display', style={'textAlign': 'center'})
    ]),

    # GAME CLOCK: Ticks every 40ms (equivalent to 25 Frames Per Second)
    dcc.Interval(id='game-clock', interval=40, n_intervals=0),
    
    # GAME STATE MEMORY: Holds all dynamic variables during gameplay
    dcc.Store(id='game-state', data={
        'bird_y': 200, 
        'velocity': 0, 
        'pipe_x': 600, 
        'pipe_hole_y': 150, 
        'score': 0, 
        'status': 'waiting',  # Can be 'waiting', 'playing', or 'game_over'
        'start_clicks': 0,    # Tracks button clicks to reset the game accurately
        'processed_jump': 0   # Timestamp of the last successful jump (for cooldown logic)
    }),
    
    # Timestamp of the last detected loud noise
    dcc.Store(id='last-jump-time', data=0)
])

# ==========================================
# 3. CALLBACK: VOICE DETECTION
# Continually listens to the 'currentVolume' (0-128) from React
# ==========================================
@app.callback(
    Output('last-jump-time', 'data'),
    Input('recorder', 'currentVolume'),
    State('last-jump-time', 'data')
)
def detect_shout(volume, last_time):
    # Do nothing if the microphone hasn't initialized
    if volume is None:
        return last_time
        
    # If the volume exceeds our calibrated threshold, record the exact time
    if volume > SHOUT_THRESHOLD:
        return time.time()
        
    return last_time

# ==========================================
# 4. CALLBACK: MAIN GAME ENGINE
# Updates physics, checks collisions, and renders the graphics
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
    
    # Fallback to prevent NoneType errors on first load
    if start_clicks is None:
        start_clicks = 0

    # START GAME LOGIC: If the button was clicked, reset everything
    if start_clicks > state.get('start_clicks', 0):
        state = {
            'bird_y': 200, 
            'velocity': -7,                     # Give the bird a slight upward bump to start
            'pipe_x': 600,                      # Spawn first pipe far away
            'pipe_hole_y': random.randint(50, 170), 
            'score': 0, 
            'status': 'playing',
            'start_clicks': start_clicks,
            'processed_jump': time.time()       # Prevent immediate jumping upon start
        }

    # UI: WAITING SCREEN
    if state['status'] == 'waiting':
        screen = html.Div([
            html.H2("Ready?", style={'marginTop': '150px', 'textAlign': 'center', 'color': '#333'})
        ])
        return state, screen, "Press START GAME to begin!"

    # UI: GAME OVER SCREEN
    if state['status'] == 'game_over':
        game_over_screen = html.Div([
            html.H1("GAME OVER!", style={'color': 'red', 'marginTop': '100px', 'textAlign': 'center'}),
            html.P("Press START GAME to try again", style={'textAlign': 'center'})
        ])
        return state, game_over_screen, f"Final Score: {state['score']} 🏆"

    # ==========================================
    # PHYSICS & MOVEMENT (Runs only while 'playing')
    # ==========================================
    now = time.time()
    
    # JUMP COOLDOWN LOGIC:
    # 1. Did the microphone pick up a shout within the last 0.20 seconds?
    # 2. Has it been at least 0.3 seconds since the LAST jump? (Prevents rapid double-jumping)
    if (now - last_jump < 0.20) and (now - state.get('processed_jump', 0) > 0.3):
        state['velocity'] = JUMP_STRENGTH
        state['processed_jump'] = now # Mark this exact time as a successful flap
        
    # Apply gravity to velocity
    state['velocity'] += GRAVITY
    
    # TERMINAL VELOCITY: Cap the maximum falling speed so the bird doesn't plummet uncontrollably
    if state['velocity'] > 10:
        state['velocity'] = 10
        
    # Apply velocity to the bird's vertical position
    state['bird_y'] += state['velocity']

    # Move the pipe leftwards
    state['pipe_x'] -= PIPE_SPEED
    if state['pipe_x'] < -50: 
        state['pipe_x'] = 450 # Reset pipe to the right side of the screen
        state['score'] += 1   # Increment score
        state['pipe_hole_y'] = random.randint(50, 170) # Generate a new random hole position

    # ==========================================
    # COLLISION DETECTION
    # ==========================================
    bird_x = 50
    bird_size = 30
    pipe_width = 50
    
    # 1. Floor and Ceiling bounds
    if state['bird_y'] > 370 or state['bird_y'] < 0:
        state['status'] = 'game_over'

    # 2. Pipe Collisions
    # Check if the bird is horizontally within the pipe area
    if (state['pipe_x'] < bird_x + bird_size) and (state['pipe_x'] + pipe_width > bird_x):
        # Check if the bird is vertically OUTSIDE the safe hole zone
        if state['bird_y'] < state['pipe_hole_y'] or (state['bird_y'] + bird_size) > (state['pipe_hole_y'] + HOLE_SIZE):
            state['status'] = 'game_over'

    # ==========================================
    # RENDERING ENGINE (HTML/CSS)
    # ==========================================
    
    # Calculate visual rotation based on velocity (falling = nose down, jumping = nose up)
    rotation = max(-20, min(90, state['velocity'] * 5))

    # Render Bird
    bird = html.Div(style={
        'position': 'absolute', 'left': f'{bird_x}px', 'top': f"{state['bird_y']}px", 
        'width': f'{bird_size}px', 'height': f'{bird_size}px', 
        'backgroundColor': '#FFD700', 'borderRadius': '50%', 'border': '2px solid black',
        'transform': f'rotate({rotation}deg)', 
        # CSS Transitions interpolate movement between frames, making 25FPS look smooth
        'transition': 'top 0.06s linear, transform 0.1s ease', 
        'boxShadow': 'inset -3px -3px 0px 0px rgba(0,0,0,0.2)'  
    })
    
    # Render Top Pipe
    pipe_top = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': '0px', 
        'width': f'{pipe_width}px', 'height': f"{state['pipe_hole_y']}px", 
        'backgroundColor': '#2E8B57', 'border': '3px solid #006400',
        'transition': 'left 0.06s linear' 
    })
    
    # Render Bottom Pipe
    pipe_bottom = html.Div(style={
        'position': 'absolute', 'left': f"{state['pipe_x']}px", 'top': f"{state['pipe_hole_y'] + HOLE_SIZE}px", 
        'width': f'{pipe_width}px', 'height': f"{400 - (state['pipe_hole_y'] + HOLE_SIZE)}px", 
        'backgroundColor': '#2E8B57', 'border': '3px solid #006400',
        'transition': 'left 0.06s linear'
    })

    return state, [bird, pipe_top, pipe_bottom], f"Score: {state['score']}"

if __name__ == '__main__':
    app.run(debug=True)