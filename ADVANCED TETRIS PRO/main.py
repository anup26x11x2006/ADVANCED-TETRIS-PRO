import pygame
import random
import time
import math
import os
from collections import defaultdict

# Initialize pygame
pygame.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 700
GRID_WIDTH = 10
GRID_HEIGHT = 20
BLOCK_SIZE = 30
GRID_OFFSET_X = (SCREEN_WIDTH - GRID_WIDTH * BLOCK_SIZE) // 2
GRID_OFFSET_Y = SCREEN_HEIGHT - GRID_HEIGHT * BLOCK_SIZE - 50

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)

# Tetrimino shapes with colors
SHAPES = [
    [[1, 1, 1, 1]],  # I
    [[1, 1], [1, 1]],  # O
    [[1, 1, 1], [0, 1, 0]],  # T
    [[1, 1, 1], [1, 0, 0]],  # J
    [[1, 1, 1], [0, 0, 1]],  # L
    [[0, 1, 1], [1, 1, 0]],  # S
    [[1, 1, 0], [0, 1, 1]]   # Z
]

SHAPES_COLORS = [CYAN, YELLOW, PURPLE, BLUE, ORANGE, GREEN, RED]

# Game states
MENU = 0
PLAYING = 1
PAUSED = 2
GAME_OVER = 3

# =================================================================
# NEW: Sound Manager (Handles missing files gracefully)
# =================================================================

class SoundManager:
    def __init__(self):
        self.sounds = {
            'rotate': self._load_sound("rotate.wav", [128]*1000),
            'move': self._load_sound("move.wav", [64]*500),
            'drop': self._load_sound("drop.wav", [200]*1500),
            'hold': self._load_sound("hold.wav", [150]*800),
            'menu': self._load_sound("menu.wav", [150]*800),
            'gameplay': self._load_sound("gameplay.wav", [150]*800),
            'gameover': self._load_sound("gameover.wav", [150]*800),
            
        }
        self.music_volume = 0.5  # 50% volume for music
        self.sfx_volume = 0.7    # 70% volume for sound effects
        self.current_music = None
        
    def _load_sound(self, filename, fallback_beep):
        try:
            return pygame.mixer.Sound(f"sounds/{filename}")
        except:
            return pygame.mixer.Sound(buffer=bytearray(fallback_beep))
    
    def play(self, name):
        sound = self.sounds.get(name)
        if sound:
            sound.set_volume(self.sfx_volume)
            sound.play()
    
# =================================================================
# NEW: Particle System for Visual Effects
# =================================================================
class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.size = random.randint(2, 5)
        self.life = random.uniform(0.5, 1.5)
        self.velocity = [random.uniform(-2, 2), random.uniform(-5, -1)]
        
    def update(self, dt):
        self.life -= dt
        self.x += self.velocity[0]
        self.y += self.velocity[1]
        return self.life > 0
        
    def draw(self, screen):
        alpha = int(255 * (self.life / 1.5))
        s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color[:3], alpha), (self.size, self.size), self.size)
        screen.blit(s, (self.x - self.size, self.y - self.size))

class Tetrimino:
    def __init__(self, shape_idx, x=GRID_WIDTH//2-2, y=0):
        self.shape = SHAPES[shape_idx]
        self.color = SHAPES_COLORS[shape_idx]
        self.x = x
        self.y = y
        self.rotation = 0
        self.shape_idx = shape_idx
        self.last_move_time = 0
        self.last_rotate_time = 0
        self.move_cooldown = 0.1
        self.rotate_cooldown = 0.2
        self.last_drop_time = 0
        self.lock_delay = 0.5
        self.lock_timer = 0
        self.locking = False
        self.t_spin = False

    def rotate(self, grid):
        original_rotation = self.rotation
        original_shape = self.shape
        
        self.rotation = (self.rotation + 1) % 4
        self.shape = [list(row) for row in zip(*self.shape[::-1])]
        
        kick_offsets = [
            [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
            [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
            [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
            [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)]
        ]
        
        for dx, dy in kick_offsets[original_rotation]:
            self.x += dx
            self.y += dy
            
            if not self.collision(grid):
                if self.shape_idx == 2:
                    corners = 0
                    test_positions = [
                        (self.x, self.y),
                        (self.x + len(self.shape[0]) - 1, self.y),
                        (self.x, self.y + len(self.shape) - 1),
                        (self.x + len(self.shape[0]) - 1, self.y + len(self.shape) - 1)
                    ]
                    
                    for tx, ty in test_positions:
                        if (tx < 0 or tx >= GRID_WIDTH or ty >= GRID_HEIGHT or 
                            (ty >= 0 and grid[ty][tx] is not None)):
                            corners += 1
                    
                    self.t_spin = (corners >= 3 and time.time() - self.last_rotate_time < 0.1)
                
                self.last_rotate_time = time.time()
                return True
            
            self.x -= dx
            self.y -= dy
        
        self.rotation = original_rotation
        self.shape = original_shape
        return False
    
    def move(self, dx, dy, grid):
        self.x += dx
        self.y += dy
        
        if self.collision(grid):
            self.x -= dx
            self.y -= dy
            return False
        
        self.last_move_time = time.time()
        
        if dy != 0:
            self.locking = False
            self.lock_timer = 0
        
        return True
    
    def hard_drop(self, grid):
        while self.move(0, 1, grid):
            pass
        self.locking = True
        self.lock_timer = self.lock_delay
        self.last_drop_time = time.time()
    
    def collision(self, grid):
        for y, row in enumerate(self.shape):
            for x, cell in enumerate(row):
                if cell:
                    board_x = self.x + x
                    board_y = self.y + y
                    
                    if (board_x < 0 or board_x >= GRID_WIDTH or 
                        board_y >= GRID_HEIGHT or 
                        (board_y >= 0 and grid[board_y][board_x] is not None)):
                        return True
        return False
    
    def update_lock_timer(self, dt):
        if self.locking:
            self.lock_timer += dt
            if self.lock_timer >= self.lock_delay:
                return True
        return False
    
    def draw(self, screen, ghost=False):
        color = self.color
        alpha = 100 if ghost else 255
        s = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
        s.fill((color[0], color[1], color[2], alpha))
        
        for y, row in enumerate(self.shape):
            for x, cell in enumerate(row):
                if cell:
                    pos_x = GRID_OFFSET_X + (self.x + x) * BLOCK_SIZE
                    pos_y = GRID_OFFSET_Y + (self.y + y) * BLOCK_SIZE
                    
                    if ghost:
                        pygame.draw.rect(screen, color, (pos_x, pos_y, BLOCK_SIZE, BLOCK_SIZE), 1)
                    else:
                        screen.blit(s, (pos_x, pos_y))
                        highlight = pygame.Surface((BLOCK_SIZE//3, BLOCK_SIZE//3), pygame.SRCALPHA)
                        highlight.fill((255, 255, 255, 50))
                        screen.blit(highlight, (pos_x + 2, pos_y + 2))
                        pygame.draw.rect(screen, WHITE, (pos_x, pos_y, BLOCK_SIZE, BLOCK_SIZE), 1)

class TetrisGame:
   
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Advanced Tetris Pro")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 24)
        self.big_font = pygame.font.SysFont('Arial', 48)
        self.high_score = self.load_high_score()  # Load high score when game starts
        
        # Initialize all essential attributes
        self.game_state = MENU  # This fixes the immediate error
        self.grid = []
        self.current_piece = None
        self.next_pieces = []
        self.held_piece = None
        self.bag = []
        self.score = 0
        self.level = 1
 #       self.lines_ed = 0
        self.combo = -1
        self.b2b = False
        self.particles = []
        self.screen_shake = 0
        
        # NEW: Enhanced systemsoundself.music = MusicManager()
        self.sound = SoundManager()
        self.reset_game()
        self.particles = []
        self.screen_shake = 0
        self.high_score = self.load_high_score()


    def load_high_score(self):
        try:
            with open("highscore.txt", "r") as f:
                return int(f.read())
        except:
            return 0
            
    def save_high_score(self):
        with open("highscore.txt", "w") as f:
            f.write(str(max(self.score, self.high_score)))

    def add_particles(self, x, y, color, count=10):
        for _ in range(count):
            self.particles.append(
                Particle(
                    GRID_OFFSET_X + x * BLOCK_SIZE + BLOCK_SIZE//2,
                    GRID_OFFSET_Y + y * BLOCK_SIZE + BLOCK_SIZE//2,
                    color
                )
            )
    
    def screen_shake_effect(self, intensity=5):
        self.screen_shake = intensity

    def reset_game(self):
        self.grid = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.current_piece = self.new_piece()
        self.next_pieces = [self.new_piece() for _ in range(5)]
        self.held_piece = None
        self.can_hold = True
        self.score = 0
        self.level = 1
        self.combo = -1
        self.game_state = MENU
        self.bag = list(range(len(SHAPES)))
        random.shuffle(self.bag)
        self.gravity = self.calculate_gravity()
        self.drop_timer = 0
        self.piece_count = 0
        self.b2b = False
        self.particles = []
        self.screen_shake = 0
        if self.game_state == MENU:
          self.sound.play('menu') 

    def new_piece(self):
        if not self.bag:
            self.bag = list(range(len(SHAPES)))
            random.shuffle(self.bag)
        
        shape_idx = self.bag.pop()
        return Tetrimino(shape_idx)
     # Try loading music

    def calculate_gravity(self):
        return 0.5  # Fixed slow speed

    def hold_piece(self):
        if not self.can_hold:
            return
        
        if self.held_piece is None:
            self.held_piece = Tetrimino(self.current_piece.shape_idx)
            self.current_piece = self.next_pieces.pop(0)
            self.next_pieces.append(self.new_piece())
        else:
            held_idx = self.held_piece.shape_idx
            self.held_piece = Tetrimino(self.current_piece.shape_idx)
            self.current_piece = Tetrimino(held_idx)
        
        self.can_hold = False
        self.current_piece.x = GRID_WIDTH // 2 - len(self.current_piece.shape[0]) // 2
        self.current_piece.y = 0
    
    
    def get_ghost_position(self):
        ghost = Tetrimino(self.current_piece.shape_idx, 
                         self.current_piece.x, self.current_piece.y)
        while not ghost.collision(self.grid):
            ghost.y += 1
        ghost.y -= 1
        return ghost
    
    def lock_piece(self):
        for y, row in enumerate(self.current_piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    board_x = self.current_piece.x + x
                    board_y = self.current_piece.y + y
                    if 0 <= board_y < GRID_HEIGHT:
                        self.grid[board_y][board_x] = self.current_piece.color
                        self.add_particles(board_x, board_y, self.current_piece.color)

        
        
        if any(self.grid[0]):
            self.game_state = GAME_OVER
            self.sound.play('gameover')
            self.save_high_score()
            return
            
        self.current_piece = self.next_pieces.pop(0)
        self.next_pieces.append(self.new_piece())
        self.can_hold = True
        self.piece_count += 1
        
        self.current_piece.x = GRID_WIDTH // 2 - len(self.current_piece.shape[0]) // 2
        self.current_piece.y = 0

        if any(self.grid[0]):
         self.game_state = GAME_OVER
         self.sound.play('gameover')
         self.save_high_score()  # Save when game ends
         return
        
        if any(self.grid[0]):
         self.sound.play('gameover')

    def draw_grid(self):
        pygame.draw.rect(self.screen, GRAY, 
                         (GRID_OFFSET_X - 2, GRID_OFFSET_Y - 2, 
                          GRID_WIDTH * BLOCK_SIZE + 4, GRID_HEIGHT * BLOCK_SIZE + 4), 0)
        
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] is not None:
                    pygame.draw.rect(self.screen, self.grid[y][x], 
                                    (GRID_OFFSET_X + x * BLOCK_SIZE, 
                                     GRID_OFFSET_Y + y * BLOCK_SIZE, 
                                     BLOCK_SIZE, BLOCK_SIZE))
                    pygame.draw.rect(self.screen, WHITE, 
                                    (GRID_OFFSET_X + x * BLOCK_SIZE, 
                                     GRID_OFFSET_Y + y * BLOCK_SIZE, 
                                     BLOCK_SIZE, BLOCK_SIZE), 1)
        
        for x in range(GRID_WIDTH + 1):
            pygame.draw.line(self.screen, (50, 50, 50), 
                            (GRID_OFFSET_X + x * BLOCK_SIZE, GRID_OFFSET_Y), 
                            (GRID_OFFSET_X + x * BLOCK_SIZE, GRID_OFFSET_Y + GRID_HEIGHT * BLOCK_SIZE))
        
        for y in range(GRID_HEIGHT + 1):
            pygame.draw.line(self.screen, (50, 50, 50), 
                            (GRID_OFFSET_X, GRID_OFFSET_Y + y * BLOCK_SIZE), 
                            (GRID_OFFSET_X + GRID_WIDTH * BLOCK_SIZE, GRID_OFFSET_Y + y * BLOCK_SIZE))
    
    def draw_info_panel(self):
        # Next pieces
        next_text = self.font.render("NEXT:", True, WHITE)
        self.screen.blit(next_text, (GRID_OFFSET_X + GRID_WIDTH * BLOCK_SIZE + 30, 50))
        
        for i, piece in enumerate(self.next_pieces[:5]):
            for y, row in enumerate(piece.shape):
                for x, cell in enumerate(row):
                    if cell:
                        pos_x = GRID_OFFSET_X + GRID_WIDTH * BLOCK_SIZE + 50 + x * BLOCK_SIZE
                        pos_y = 100 + i * 100 + y * BLOCK_SIZE
                        pygame.draw.rect(self.screen, piece.color, 
                                        (pos_x, pos_y, BLOCK_SIZE, BLOCK_SIZE))
                        pygame.draw.rect(self.screen, WHITE, 
                                        (pos_x, pos_y, BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Hold piece
        hold_text = self.font.render("HOLD:", True, WHITE)
        self.screen.blit(hold_text, (GRID_OFFSET_X - 150, 50))
        
        if self.held_piece:
            for y, row in enumerate(self.held_piece.shape):
                for x, cell in enumerate(row):
                    if cell:
                        pos_x = GRID_OFFSET_X - 130 + x * BLOCK_SIZE
                        pos_y = 100 + y * BLOCK_SIZE
                        pygame.draw.rect(self.screen, self.held_piece.color, 
                                        (pos_x, pos_y, BLOCK_SIZE, BLOCK_SIZE))
                        pygame.draw.rect(self.screen, WHITE, 
                                        (pos_x, pos_y, BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Score and level
        score_text = self.font.render(f"SCORE: {self.score}", True, WHITE)
        level_text = self.font.render(f"LEVEL: {self.level}", True, WHITE)
        high_score_text = self.font.render(f"HIGH: {self.high_score}", True, YELLOW)
        
        self.screen.blit(score_text, (GRID_OFFSET_X - 150, 250))
        self.screen.blit(level_text, (GRID_OFFSET_X - 150, 300))
        self.screen.blit(high_score_text, (GRID_OFFSET_X - 150, 200))
        
        # Combo
        if self.combo > 0:
            combo_text = self.font.render(f"COMBO: {self.combo}", True, WHITE)
            self.screen.blit(combo_text, (GRID_OFFSET_X - 150, 400))
        
        # T-spin indicator
        if self.current_piece.t_spin:
            tspin_text = self.font.render("T-SPIN!", True, YELLOW)
            self.screen.blit(tspin_text, (GRID_OFFSET_X - 150, 450))
        
        # Back-to-back indicator
        if self.b2b:
            b2b_text = self.font.render("B2B", True, ORANGE)
            self.screen.blit(b2b_text, (GRID_OFFSET_X - 150, 500))

        high_score_text = self.font.render(f"HIGH: {self.high_score}", True, YELLOW)
        self.screen.blit(high_score_text, (GRID_OFFSET_X - 150, 200))    
    
    def draw_menu(self):
        title = self.big_font.render("ADVANCED TETRIS PRO", True, WHITE)
        start_text = self.font.render("Press ENTER to Start", True, WHITE)
        controls_text1 = self.font.render("Controls:", True, WHITE)
        controls_text2 = self.font.render("Left/Right: Move", True, WHITE)
        controls_text3 = self.font.render("Up: Rotate", True, WHITE)
        controls_text4 = self.font.render("Down: Soft Drop", True, WHITE)
        controls_text5 = self.font.render("Space: Hard Drop", True, WHITE)
        controls_text6 = self.font.render("C: Hold", True, WHITE)
        controls_text7 = self.font.render("P: Pause", True, WHITE)
        
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
        self.screen.blit(start_text, (SCREEN_WIDTH // 2 - start_text.get_width() // 2, 300))
        self.screen.blit(controls_text1, (SCREEN_WIDTH // 2 - controls_text1.get_width() // 2, 400))
        self.screen.blit(controls_text2, (SCREEN_WIDTH // 2 - controls_text2.get_width() // 2, 450))
        self.screen.blit(controls_text3, (SCREEN_WIDTH // 2 - controls_text3.get_width() // 2, 480))
        self.screen.blit(controls_text4, (SCREEN_WIDTH // 2 - controls_text4.get_width() // 2, 510))
        self.screen.blit(controls_text5, (SCREEN_WIDTH // 2 - controls_text5.get_width() // 2, 540))
        self.screen.blit(controls_text6, (SCREEN_WIDTH // 2 - controls_text6.get_width() // 2, 570))
        self.screen.blit(controls_text7, (SCREEN_WIDTH // 2 - controls_text7.get_width() // 2, 600))
    
    def draw_pause(self):
        pause_text = self.big_font.render("PAUSED", True, WHITE)
        continue_text = self.font.render("Press P to Continue", True, WHITE)
        quit_text = self.font.render("Q: Quit to Menu", True, RED)
        
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 128))
        self.screen.blit(s, (0, 0))
        
        self.screen.blit(pause_text, (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(continue_text, (SCREEN_WIDTH // 2 - continue_text.get_width() // 2, SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(quit_text, (SCREEN_WIDTH // 2 - quit_text.get_width() // 2, SCREEN_HEIGHT // 2 + 90))
    
    def draw_game_over(self):
        over_text = self.big_font.render("GAME OVER", True, RED)
        score_text = self.font.render(f"Final Score: {self.score}", True, WHITE)
        high_score_text = self.font.render(f"High Score: {max(self.score, self.high_score)}", True, YELLOW)
        restart_text = self.font.render("Press ENTER to Restart", True, WHITE)
        
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.screen.blit(s, (0, 0))
        
        self.screen.blit(over_text, (SCREEN_WIDTH // 2 - over_text.get_width() // 2, SCREEN_HEIGHT // 2 - 100))
        self.screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2 - 20))
        self.screen.blit(high_score_text, (SCREEN_WIDTH // 2 - high_score_text.get_width() // 2, SCREEN_HEIGHT // 2 + 40))
        self.screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 100))
    
    def update(self, dt):
        if self.game_state == PLAYING:
            self.drop_timer += dt
            if self.drop_timer >= self.gravity:
                if not self.current_piece.move(0, 1, self.grid):
                    self.current_piece.locking = True
                self.drop_timer = 0
            
            if self.current_piece.update_lock_timer(dt):
                self.lock_piece()
    
    def draw(self):
        self.screen.fill(BLACK)
        
        # Apply screen shake
        shake_offset = (
            random.uniform(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0,
            random.uniform(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0
        )
        self.screen_shake = max(0, self.screen_shake - 1)
        
        # Draw particles
        for p in self.particles[:]:
            if not p.update(1/60):
                self.particles.remove(p)
            else:
                p.draw(self.screen)
        
        if self.game_state == MENU:
            self.draw_menu()
        elif self.game_state == GAME_OVER:
            self.draw_grid()
            self.draw_info_panel()
            self.draw_game_over()
        else:
            self.draw_grid()
            self.draw_info_panel()
            ghost = self.get_ghost_position()
            ghost.draw(self.screen, ghost=True)
            self.current_piece.draw(self.screen)
            
            if self.game_state == PAUSED:
                self.draw_pause()
        
        pygame.display.flip()
    
    def load_high_score(self):
      try:
          with open("highscore.txt", "r") as f:
              return int(f.read())
      except (FileNotFoundError, ValueError):
          return 0  # Return 0 if file doesn't exist or is invalid

    def save_high_score(self):
        with open("highscore.txt", "w") as f:
            f.write(str(max(self.score, self.high_score)))

    def run(self):
        running = True
        last_time = time.time()
        
        while running:
            dt = time.time() - last_time
            last_time = time.time()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    current_time = time.time()
                    
                    if event.key == pygame.K_LEFT:
                        if current_time - self.current_piece.last_move_time > self.current_piece.move_cooldown:
                            if self.current_piece.move(-1, 0, self.grid):
                                self.sound.play('move')
                    elif event.key == pygame.K_RIGHT:
                        if current_time - self.current_piece.last_move_time > self.current_piece.move_cooldown:
                            if self.current_piece.move(1, 0, self.grid):
                                self.sound.play('move')
                    elif event.key == pygame.K_UP:
                        if current_time - self.current_piece.last_rotate_time > self.current_piece.rotate_cooldown:
                            if self.current_piece.rotate(self.grid):
                                self.sound.play('rotate')
                    elif event.key == pygame.K_DOWN:
                        if current_time - self.current_piece.last_move_time > self.current_piece.move_cooldown:
                            if self.current_piece.move(0, 1, self.grid):
                                self.sound.play('move')
                    elif event.key == pygame.K_SPACE:
                        self.current_piece.hard_drop(self.grid)
                        self.sound.play('drop')
                        self.screen_shake_effect(2)
                    elif event.key == pygame.K_c:
                        if self.can_hold:
                            self.sound.play('hold')
                            self.hold_piece()
                    elif event.key == pygame.K_p:
                        if self.game_state == PLAYING:
                            self.game_state = PAUSED
                            self.sound.play('hold')
                        elif self.game_state == PAUSED:
                            self.sound.play('hold')
                            self.game_state = PLAYING
                    elif event.key == pygame.K_q and self.game_state == PAUSED:
                        self.game_state = MENU
                        self.sound.play('menu')
                    elif event.key == pygame.K_RETURN:
                            if self.game_state == GAME_OVER:
                                self.reset_game()
                                self.sound.play('gameover')
                            self.game_state = PLAYING
                            self.sound.play('gameplay')
            self.update(dt)
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()

if __name__ == "__main__":
    # Create required directories
    os.makedirs("sounds", exist_ok=True)
    game = TetrisGame()
    game.run()