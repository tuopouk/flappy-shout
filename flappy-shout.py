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
IS_LOCAL = os.environ.get('PORT') is None

if IS_LOCAL:
    TICK_RATE = 40
    CSS_TRANSITION = '0.04s linear'
    GRAVITY = 1.5         
    JUMP_STRENGTH = -12   
    PIPE_SPEED = 10       
    JUMP_COOLDOWN = 0.2
else:
    TICK_RATE = 150
    CSS_TRANSITION = '0.15s linear'
    GRAVITY = 4.0         
    JUMP_STRENGTH = -22   
    PIPE_SPEED = 20       
    JUMP_COOLDOWN = 0.4

HOLE_SIZE = 170       

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
            html.H1("Ploply 🐣🗣️", className="text-center mt-3 mb-1"),
            html.P("1. Click Mic 👉 2. SHOUT to Start!", 
                   className="text-center fw-bold mb-2 text-primary"),
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

    dbc.Row(className="justify-content-center mb-3", children=[
        dbc.Col(width=10, md=6, children=[
            html.Div("Microphone Sensitivity", 
                     className="text-center text-muted fw-bold", 
                     style={'fontSize': '11px', 'marginBottom': '5px'}),
            dcc.Slider(
                id='sensitivity-slider',
                min=5, max=100, step=5, value=40,
                marks={10: 'PC Mic', 40: 'Mobile', 80: 'Loud'},
                updatemode='drag',
                className="p-0"
            )
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

    dcc.Interval(id='game-clock', interval=TICK_RATE, n_intervals=0, disabled=True),
    
    # LISÄTTY: 'death_time' pitää kirjaa kuolinhetkestä
    dcc.Store(id='game-state', data={
        'bird_y': 200, 'velocity': 0, 'pipe_x': 400, 'pipe_hole_y': 150, 
        'score': 0, 'status': 'waiting', 'processed_jump': 0, 'death_time': 0
    }),
    
    dcc.Store(id='last-jump-time', data=0)

], fluid=True, className="pb-5")

# ==========================================
# 4. CALLBACK: VOLUME METER
# ==========================================
@app.callback(
    Output('meter-fill', 'style'),
    Input('recorder', 'currentVolume'),
    Input('sensitivity-slider', 'value')
)
def update_volume_meter(volume, threshold):
    if volume is None: return {'width': '0%', 'height': '100%', 'backgroundColor': '#198754'}
    pct = min(100, (volume / 128) * 100)
    color = '#dc3545' if volume > threshold else '#198754'
    return {'width': f'{pct}%', 'height': '100%', 'backgroundColor': color, 'transition': 'width 0.1s ease'}

# ==========================================
# 5. CALLBACK: CLIENTSIDE VOICE DETECTION
# ==========================================
app.clientside_callback(
    """
    function(volume, threshold, last_time) {
        if (!volume || volume < threshold) return window.dash_clientside.no_update; 
        return Date.now() / 1000.0; 
    }
    """,
    Output('last-jump-time', 'data'),
    Input('recorder', 'currentVolume'),
    State('sensitivity-slider', 'value'),
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
    Input('last-jump-time', 'data'),  
    State('game-state', 'data')
)
def update_game(n, last_jump, state):
    trigger = ctx.triggered_id
    now = time.time()
    is_shouting = (now - last_jump < 0.50)

    # 1. VALIKKOTILAT: Odotus tai Game Over
    if state['status'] in ['waiting', 'game_over']:
        can_start = False
        
        if is_shouting:
            if state['status'] == 'waiting':
                can_start = True
            elif state['status'] == 'game_over':
                # RESTART-LOGIIKKA: Varmistetaan, että kuolemasta on kulunut yli 1.0 sekuntia
                # JA että huuto on tapahtunut kuoleman jälkeen (ei paniikkihuutoa).
                death_time = state.get('death_time', 0)
                if (now - death_time > 1.0) and (last_jump > death_time):
                    can_start = True

        if can_start:
            state = {
                'bird_y': 200, 'velocity': -15, 'pipe_x': 400, 
                'pipe_hole_y': random.randint(50, 170), 'score': 0, 
                'status': 'playing', 'processed_jump': now, 'death_time': 0
            }
        else:
            if state['status'] == 'waiting':
                screen = html.H2("SHOUT TO START!", className="text-center text-primary fw-bold", style={'marginTop': '150px'})
                return state, screen, "Turn on Mic first!", True 
            else:
                screen = html.Div([
                    html.H1("GAME OVER!", className="text-center text-danger fw-bold", style={'marginTop': '80px'}),
                    html.H3("SHOUT TO RESTART!", className="text-center text-primary mt-4")
                ])
                return state, screen, f"Score: {state['score']} 🏆", True 

    if trigger == 'game-clock' and state['status'] != 'playing':
        raise PreventUpdate

    # --- PHYSICS ---
    if is_shouting and (now - state.get('processed_jump', 0) > JUMP_COOLDOWN):
        state['velocity'] = JUMP_STRENGTH
        state['processed_jump'] = now 
        
    state['velocity'] += GRAVITY
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
    collision = False
    
    if state['bird_y'] > 370 or state['bird_y'] < 0:
        collision = True
    elif (state['pipe_x'] < bird_x + bird_size) and (state['pipe_x'] + pipe_width > bird_x):
        if state['bird_y'] < state['pipe_hole_y'] or (state['bird_y'] + bird_size) > (state['pipe_hole_y'] + HOLE_SIZE):
            collision = True

    if collision:
        state['status'] = 'game_over'
        state['death_time'] = now  # <--- TALLENNETAAN KUOLINHETKI

    # --- RENDERING ---
    rot_multiplier = 4 if IS_LOCAL else 2.5
    rotation = max(-20, min(90, state['velocity'] * rot_multiplier))
    
    bird = html.Div("🐣", style={
        'position': 'absolute', 'left': '0px', 'top': '0px',
        'width': f'{bird_size}px', 'height': f'{bird_size}px', 
        'fontSize': '26px', 'textAlign': 'center', 'lineHeight': f'{bird_size}px',
        'transform': f'translate3d({bird_x}px, {state["bird_y"]}px, 0) rotate({rotation}deg)', 
        'transition': f'transform {CSS_TRANSITION}'
    })
    
    pipe_top = html.Div(style={
        'position': 'absolute', 'left': '0px', 'top': '0px', 
        'width': f'{pipe_width}px', 'height': f"{state['pipe_hole_y']}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 
        'transform': f'translate3d({state["pipe_x"]}px, 0, 0)',
        'transition': f'transform {CSS_TRANSITION}'
    })
    
    pipe_bottom = html.Div(style={
        'position': 'absolute', 'left': '0px', 'top': '0px', 
        'width': f'{pipe_width}px', 'height': f"{400 - (state['pipe_hole_y'] + HOLE_SIZE)}px", 
        'backgroundColor': '#198754', 'border': '3px solid #146c43', 
        'transform': f'translate3d({state["pipe_x"]}px, {state["pipe_hole_y"] + HOLE_SIZE}px, 0)',
        'transition': f'transform {CSS_TRANSITION}'
    })

    return state, [bird, pipe_top, pipe_bottom], f"Score: {state['score']}", False

if __name__ == '__main__':
    app.run(debug=False)