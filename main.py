import pygame
import textwrap
import sys
import re 
import statistics
import urllib.request

import hashlib

pygame.init()

# Game Layout/demensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 640
FPS = 60

# Colours that will be used within the game
WHITE = (255, 255, 255)
RED = (213, 55, 55)
BLUE = (55, 125, 213)
BLACK = (20, 20, 20)
GREEN = (46, 139, 87)
LIGHT_GRAY = (240, 244, 248)
TEXT_MUTED = (100, 116, 139)
SILHOUETTE_COLOR = (80, 80, 80)

FONT_TITLE = pygame.font.SysFont("Arial", 26, bold=True)
FONT_MED = pygame.font.SysFont("Arial", 22)
FONT_SMALL = pygame.font.SysFont("Arial", 16)
quiz_box_rect = pygame.Rect(200, 50, 560, 130)

game_state = "LOGIN" 
player_email = ""
player_age = ""
player_country = ""
parent_email = "" 
active_input_field = "EMAIL"  

# consent text to be displayed to player before starting the game, ensuring they understand data collection and usage and
# minors are not allowed to participate without parental consent which will be gained through entering a valid parental email 
# This is a critical step for ethical data collection and compliance with privacy regulations (most important part for this project)
consent_lines = [
    "DATA PROCESSING &",
    "REACTION TIME STUDY CONSENT",
    "",
    "1. By clicking 'AGREE', you confirm you are voluntarily participating.",
    "2. Your reaction times and typing accuracy will be anonymously logged.",
    "3. Demographics (Age, Country) will be used solely for tracking trends.",
    "4. Your email will be used once to create an anonymous ID code",
    "   and your actual email is never stored.",
    "5. Minors (under 16): You confirm a parent/guardian has given permission",
    "   and provided their email.",
    "6. You retain the right to withdraw at any point and request that your",
    "   data deleted at any time.",
    "",
    "Press [Y] to AGREE & start game  |  Press [N] to DECLINE & close program"
]

error_message = ""

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()) is not None

# uploading data to Google Forms
import requests
import re

def send_to_google_form(anon_id, age, country, think_ms, total_ms, sd_ms, acc):
    form_id = "1FAIpQLSdQ1bV2GyLzzWiVOoV40tpuL2IksUjm1WvY0qcXxsx7Xwm2oA"
    view_url = f"https://docs.google.com/forms/d/e/{form_id}/viewform"
    post_url = f"https://docs.google.com/forms/d/e/{form_id}/formResponse"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": view_url
    }
    
    try:
        session = requests.Session()
        get_res = session.get(view_url, headers=headers, timeout=8)
        fbzx_match = re.search(r'name="fbzx"\s+value="([^"]+)"', get_res.text)
        fbzx_val = fbzx_match.group(1) if fbzx_match else ""
        
        form_data = {
            "entry.294342726": str(anon_id),
            "entry.981105864": str(age),
            "entry.428908552": str(country),
            "entry.1040684020": str(round(think_ms, 2)),
            "entry.129133565": str(round(total_ms, 2)),
            "entry.197259883": str(round(sd_ms, 2)),
            "entry.2087740991": str(round(acc, 1)),
            "fvv": "1",
            "pageHistory": "0",
            "fbzx": fbzx_val
        }
        
        post_res = session.post(post_url, data=form_data, headers=headers, timeout=8)
        if post_res.status_code == 200:
            print("[SUCCESS] Results sent straight to STRIPE YSTE Google Sheet!")
        else:
            print(f"[WARNING] Google returned status {post_res.status_code} | URL: {post_url}")
    except Exception as e:
        print(f"Upload error: {e}")

# --- ENEMY CLASS -> used to create multiple enemies with unique questions and
#  answers with the exact amount for the same amount of questions in the pool.
#  The enemies will move towards the player until they reach a certain distance at which point they will pause 
# and wait for the input from the player. The player's reaction time will be tracked from the moment the enemy 
# appears on the screen until the player inputs an answer, whether that answer is correct or incorrect.
class Enemy:
    def __init__(self, x, y, width, height, speed, question, answer, name):
        self.rect = pygame.Rect(x, y, 50, 50)
        self.speed = speed
        self.question = question
        self.answer = answer
        self.name = name
        self.is_paused = False
        self.has_damaged = False  
        self.spawn_time = 0
        self.time_tracked = False 
        self.first_key_time = 0

    def update(self, player_x, stop_distance):
        # Start the timer once the enemy enters onto the screen 
        if self.rect.x < SCREEN_WIDTH and not self.time_tracked:
            self.spawn_time = pygame.time.get_ticks()
            self.time_tracked = True

        # Check distance to pause
        distance_to_player = self.rect.left - player_x
        if distance_to_player <= stop_distance and not self.has_damaged:
            self.is_paused = True

        # Move left if (the enemy is) not paused
        if not self.is_paused:
            self.rect.x -= self.speed

    def draw(self, surface):
        pygame.draw.rect(surface, RED, self.rect)


screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Stripe YSTE Project")
clock = pygame.time.Clock()

player_rect = pygame.Rect(100, 270, 50, 50)
STOP_THRESHOLD = 200  
score = 0

# List of questions and answers for the game that users will be asked to answer. Each question tests a different part of cognitive ability, 
# memory, and reaction time. The answers are stored in a way that allows for easy comparison with user input. 
# The results from these questions will be used to analyze player's reaction time and accuracy, creating a 
# baseline for building cognitive reserve and flagging potential cognitive decline. 
QUESTION_POOL = [
    {"q": "What is the English translation for 'Samhain'?", "a": "november", "name": "Samhain"},
    {"q": "Click the 'a' key once you have memorised these Irish words: 'fiche, corcra, balla'", "a": "a", "name": "Irish Words"},
    {"q": "Cén bhliain atá ann faoi láthair?", "a": "2026", "name": "Current Year"},
    {"q": "In Irish, name the object shown in the image silhouette", "a": "crann", "name": "Tree"},
    {"q": "From the list of words, type the one that translates the list memorised from question 2: 'house, twenty, ball'", "a": "twenty", "name": "Memorised Words"},
    {"q": "Spell 'baile' backwards", "a": "eliab", "name": "Spell Backwards"},
    {"q": "Spell 'dearg' backwards", "a": "graed", "name": "Spell Backwards 2"},
    {"q": "Coinnigh an barra spáis síos", "a": "HOLD_SPACE", "name": "Irish Translation"},
    {"q": "Write a simple Irish sentence containing a noun and a verb", "a": "IRISH_SENTENCE", "name": "Irish Sentence"},
    {"q": "Counting backwards from 100 by sevens, what is the 5th number? Write in numbers.", "a": "65", "name": "Counting Backwards"},
]

async def main():
    game_state = "LOGIN"
    player_email = ""
    player_age = ""
    player_country = ""
    parent_email = ""
    error_message = ""
    player_input = ""
    active_input_field = "EMAIL"

def validate_irish_sentence(text):
    """Accept a short Irish sentence using a common noun and a verb."""
    cleaned = text.strip().lower()
    if len(cleaned) < 5:
        return False

    nouns = {"madra", "teach", "bád", "crann", "bean", "fear", "cailin", "scoil", "cuid", "muc", "ceapaire", "siopa", "máthair", "cara", "clann", "oíche", "maidin", "am", "aois", "doras","usice", "bainne", "tae", "arán", "gruaig", "prataí", "sicín", "bricfeásta", "d'aois", "slán", "maith", "brón"}
    verbs = {"tá", "ag", "rith", "ith", "d'ith", "oscail", "dún", "scríobh", "bí", "feic", "chuaigh", "imir", "ól","cuir", "clois", "éist", "bris", "ceannaigh", "léigh", "buail", "rinne", "ithim", "itheann", "tá mé go", "is mise", "is maith liom", "ní maith liom", "bhí", "is aoibhinn liom"}

    words = re.findall(r"[a-záéíóú]+", cleaned)
    if not words:
        return False

    has_noun = any(word in nouns for word in words)
    has_verb = any(word in verbs for word in words)
    return has_noun and has_verb


def record_reaction_time(enemy, timestamp):
    if enemy.time_tracked:
        q_latency = timestamp - enemy.spawn_time
        if q_latency > 150:
            active_session_latencies.append(q_latency)

    if enemy.first_key_time > 0:
        end_think = enemy.first_key_time
        think_lat = end_think - enemy.spawn_time
        if think_lat > 150:
            thinking_latencies.append(think_lat)


# make sure questions all used, in order and never repeated -> player must answer all questions that are given as
# they all test different parts of cognition
enemy_queue = []
for q_data in QUESTION_POOL:
    
    # Spawn all the enemies at 850 (off screen) and since only enemy_queue[0] moves (one enemy at a time), 
    # the next one will immediately enter from 850 as soon as the player answers the question.
    new_enemy = Enemy(
        x=850,
        y=270,
        width=50,
        height=50,
        speed=3,
        question=q_data["q"],
        answer=q_data["a"],
        name=q_data["name"]
    )
    enemy_queue.append(new_enemy)


total_level_enemies = len(QUESTION_POOL)
player_input = ""
active_session_latencies = []
thinking_latencies = []
total_attempts = 0
correct_attempts = 0
data_exported = False
score = 0
STOP_THRESHOLD = 50
player_rect = pygame.Rect(50, 270, 50, 50)
space_hold_start_time = 0
answered_questions = 0


def draw_wrapped_text(surface, text, font, color, rect):
    """Render text inside a rectangle and wrap long lines to fit the box."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        candidate = f"{current_line} {word}".strip()
        if font.size(candidate)[0] <= rect.width:
            current_line = candidate
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    y = rect.y
    for line in lines:
        surface.blit(font.render(line, True, color), (rect.x, y))
        y += font.get_linesize() + 4

    return lines


# Main game loop/what the player sees and will be player
# the questions will be answered here and from this longitudinal data will be collected from these responses over time
running = True
while running:
    current_time = pygame.time.get_ticks()
    active_enemy = enemy_queue[0] if len(enemy_queue) > 0 else None

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if game_state == "LOGIN":
                if event.key == pygame.K_RETURN:
                    if is_valid_email(player_email):
                        game_state = "SURVEY"
                        active_input_field = "AGE"
                        error_message = ""
                    else:
                        error_message = "Please enter a valid email format!"
                elif event.key == pygame.K_BACKSPACE:
                    player_email = player_email[:-1]
                else:
                    if len(player_email) < 35:
                        player_email += event.unicode

            elif game_state == "SURVEY":
                if event.key == pygame.K_TAB or event.key == pygame.K_RETURN:
                    if active_input_field == "AGE":
                        if player_age.strip().isdigit() and 4 < int(player_age) < 110:
                            active_input_field = "COUNTRY"
                            error_message = ""
                        else:
                            error_message = "Please enter a valid numerical age!"
                    elif active_input_field == "COUNTRY":
                        if len(player_country.strip()) >= 2:
                            if int(player_age) < 16:
                                active_input_field = "PARENT_EMAIL"
                                error_message = ""
                            else:
                             game_state = "CONSENT"
                            error_message = ""
                        else:
                            error_message = "Please enter your country name!"
                                 
                    elif active_input_field == "PARENT_EMAIL":
                        if is_valid_email(parent_email) and parent_email.strip().lower() != player_email.strip().lower():
                            game_state = "CONSENT"
                            error_message = ""
                        else:
                            error_message = "Enter a valid parent email (different from yours)!"

                elif event.key == pygame.K_BACKSPACE:
                    if active_input_field == "AGE":
                        player_age = player_age[:-1]
                    else:
                        player_country = player_country[:-1]
                else:
                    if active_input_field == "AGE" and event.unicode.isdigit() and len(player_age) < 3:
                        player_age += event.unicode
                    elif active_input_field == "COUNTRY" and event.unicode.isalpha() and len(player_country) < 25:
                        player_country += event.unicode
                    elif active_input_field == "PARENT_EMAIL" and len(parent_email) < 35 and event.unicode.isprintable():
                        parent_email += event.unicode

            elif game_state == "CONSENT":
                if event.key == pygame.K_y:
                    game_state = "PLAYING"
                elif event.key == pygame.K_n:
                    running = False

            elif game_state == "PLAYING" and active_enemy:
                if active_enemy.answer == "HOLD_SPACE":
                    if event.key == pygame.K_SPACE and space_hold_start_time == 0:
                        space_hold_start_time = current_time
                elif event.key == pygame.K_RETURN:
                    total_attempts += 1
                    if active_enemy.answer == "IRISH_SENTENCE":
                        answer_is_correct = validate_irish_sentence(player_input)
                    else:
                        answer_is_correct = player_input.strip().lower() == active_enemy.answer.lower()

                    if answer_is_correct:
                        score += 3
                        correct_attempts += 1
                    else:
                        score -= 3
                        active_enemy.is_paused = False

                    if active_enemy.time_tracked:
                        q_latency = current_time - active_enemy.spawn_time
                        if q_latency > 150:
                            active_session_latencies.append(q_latency)

                        end_think = active_enemy.first_key_time if active_enemy.first_key_time > 0 else current_time
                        think_lat = end_think - active_enemy.spawn_time
                        if think_lat > 150:
                            thinking_latencies.append(think_lat)

                    answered_questions += 1
                    enemy_queue.pop(0)
                    player_input = ""
                    space_hold_start_time = 0
                elif event.key == pygame.K_BACKSPACE:
                    player_input = player_input[:-1]
                else:
                    if active_enemy.time_tracked and active_enemy.first_key_time == 0:
                        active_enemy.first_key_time = current_time
                    if event.unicode and event.unicode.isprintable():
                        player_input += event.unicode
            elif game_state == "VICTORY":
                if event.key in [pygame.K_r, pygame.K_RETURN]:
                    game_state = "LOGIN"
                    player_email = ""
                    player_age = ""
                    player_country = ""
                    parent_email = ""
                    error_message = ""
                    player_input = ""
                    active_input_field = "EMAIL"

                    score = 0
                    total_attempts = 0
                    correct_attempts = 0
                    answered_questions = 0
                    active_session_latencies = []
                    thinking_latencies = []
                    space_hold_start_time = 0
                    data_exported = False

                    enemy_queue = [Enemy(850, 270, 50, 50, 3, qd["q"], qd["a"], qd["name"]) for qd in QUESTION_POOL]

        elif event.type == pygame.KEYUP and game_state == "PLAYING" and active_enemy and active_enemy.answer == "HOLD_SPACE":
            if event.key == pygame.K_SPACE and space_hold_start_time > 0:
                hold_time = current_time - space_hold_start_time
                total_attempts += 1
                answer_is_correct = hold_time >= 1500

                if answer_is_correct:
                    score += 3
                    correct_attempts += 1
                else:
                    score -= 3

                if active_enemy.time_tracked:
                    record_reaction_time(active_enemy, current_time)

                answered_questions += 1
                enemy_queue.pop(0)
                player_input = ""
                space_hold_start_time = 0

    if game_state == "PLAYING":
        if active_enemy:
            active_enemy.update(player_rect.right, STOP_THRESHOLD)
            if player_rect.colliderect(active_enemy.rect) and not active_enemy.has_damaged:
                score -= 3
                active_enemy.has_damaged = True
                active_enemy.is_paused = True
                if active_enemy.time_tracked:
                    q_latency = current_time - active_enemy.spawn_time
                    if q_latency > 150:
                        active_session_latencies.append(q_latency)
        else:
            game_state = "VICTORY"

    if game_state == "VICTORY" and not data_exported:
        print(f"[DEBUG] Reached VICTORY! Latencies recorded: {len(active_session_latencies)}")
        
        if len(active_session_latencies) > 0:
            avg_total = sum(active_session_latencies) / len(active_session_latencies)
            avg_think = sum(thinking_latencies) / len(thinking_latencies) if thinking_latencies else avg_total
            consistency_sd = statistics.stdev(active_session_latencies) if len(active_session_latencies) > 1 else 0
            accuracy_pct = (correct_attempts / total_attempts) * 100 if total_attempts > 0 else 0
            anon_id = hashlib.sha256(player_email.strip().lower().encode()).hexdigest()[:12]

            print("Uploading metrics directly to your cloud sheet dashboard...")
            send_to_google_form(anon_id, player_age.strip(), player_country.strip(), avg_think, avg_total, consistency_sd, accuracy_pct)
        else:
            print("[WARNING] No latencies were recorded during this run!")
            
        data_exported = True

    # render: 
    screen.fill(LIGHT_GRAY)

    if game_state == "LOGIN":
        box_y = 240
        pygame.draw.rect(screen, WHITE, (150, 130, 500, 300), 0, 8)
        lbl_title = FONT_TITLE.render("Create Player Session", True, BLACK)
        lbl_sub = FONT_MED.render("Enter your email address:", True, BLACK)
        screen.blit(lbl_title, (240, 160))
        screen.blit(lbl_sub, (180, 210))

        pygame.draw.rect(screen, BLACK, (180, box_y, 440, 45), 2, 4)
        txt_surf = FONT_MED.render(player_email, True, BLUE)
        screen.blit(txt_surf, (190, box_y + 8))

        if error_message:
            err_surf = FONT_SMALL.render(error_message, True, RED)
            screen.blit(err_surf, (180, box_y + 55))
        else:
            hint_surf = FONT_SMALL.render("Press [ENTER] to confirm email address", True, TEXT_MUTED)
            screen.blit(hint_surf, (180, box_y + 55))

    elif game_state == "SURVEY":
        pygame.draw.rect(screen, WHITE, (150, 100, 500, 380), 0, 8)
        lbl_title = FONT_TITLE.render("Demographic Information", True, BLACK)
        screen.blit(lbl_title, (260, 130))

        lbl_age = FONT_MED.render("1. Age (Years):", True, BLACK)
        screen.blit(lbl_age, (180, 190))
        border_age = 3 if active_input_field == "AGE" else 1
        pygame.draw.rect(screen, BLUE if active_input_field == "AGE" else BLACK, (180, 225, 440, 40), border_age, 4)
        age_surf = FONT_MED.render(player_age, True, BLACK)
        screen.blit(age_surf, (190, 232))

        lbl_cnt = FONT_MED.render("2. Current Country Location:", True, BLACK)
        screen.blit(lbl_cnt, (180, 285))
        border_cnt = 3 if active_input_field == "COUNTRY" else 1
        pygame.draw.rect(screen, BLUE if active_input_field == "COUNTRY" else BLACK, (180, 320, 440, 40), border_cnt, 4)
        cnt_surf = FONT_MED.render(player_country, True, BLACK)
        screen.blit(cnt_surf, (190, 327))

        if active_input_field == "PARENT_EMAIL":
            screen.blit(FONT_MED.render("3. Parent/Guardian Email (Required Under 16):", True, RED), (180, 320))
            pygame.draw.rect(screen, BLUE, (180, 350, 440, 38), 2, 4)
            screen.blit(FONT_MED.render(parent_email, True, BLACK), (190, 357))
            hint_y = 405
        else:
            hint_y = 325

        if error_message:
            err_surf = FONT_SMALL.render(error_message, True, RED)
            screen.blit(err_surf, (180, 375))
        else:
            hint_surf = FONT_SMALL.render("Press [ENTER] to swap sections", True, TEXT_MUTED)
            screen.blit(hint_surf, (180, 375))

           elif game_state == "CONSENT":
        pygame.draw.rect(screen, WHITE, (30, 30, 740, 540), 0, 8)
        pygame.draw.rect(screen, BLACK, (30, 30, 740, 540), 2, 8)

        font_consent_title = pygame.font.Font(None, 26)
        font_consent_body = pygame.font.Font(None, 21)
        font_consent_action = pygame.font.Font(None, 23)

        current_y = 50
        for index, text_line in enumerate(consent_lines):
            if text_line.strip() == "":
                current_y += 10
                continue

            if index == 0:
                font_to_use = font_consent_title
                line_color = BLACK
                char_limit = 65
            elif index == len(consent_lines) - 1:
                font_to_use = font_consent_action
                line_color = GREEN
                char_limit = 70
            else:
                font_to_use = font_consent_body
                line_color = BLACK
                char_limit = 82
                
            for wrapped_part in textwrap.wrap(text_line, width=char_limit):
                surf_line = font_to_use.render(wrapped_part, True, line_color)
                screen.blit(surf_line, (50, current_y))
                current_y += font_to_use.get_linesize() + 3
            current_y += 4

    elif game_state == "PLAYING":
        screen.fill(WHITE)
        pygame.draw.rect(screen, BLUE, player_rect)
        if active_enemy:
            active_enemy.draw(screen)
        score_surface = FONT_MED.render(f"Score: {score}", True, BLACK)
        screen.blit(score_surface, (20, 20))
        if active_enemy:
            pygame.draw.rect(screen, BLACK, quiz_box_rect, 2, 4)
            question_lines = draw_wrapped_text(
                screen,
                f"Solve: {active_enemy.question}",
                FONT_SMALL,
                BLACK,
                pygame.Rect(220, 55, 520, 100),
            )
            lines_drawn = len(question_lines)
            screen.blit(FONT_SMALL.render(f"Your Answer: {player_input}", True, GREEN), (220, 90))

            if active_enemy.name == "Tree":
                pygame.draw.rect(screen, SILHOUETTE_COLOR, (715, 95, 16, 45))
                pygame.draw.circle(screen, SILHOUETTE_COLOR, (723, 75), 26)
                pygame.draw.circle(screen, SILHOUETTE_COLOR, (723, 50), 20)

            dy_y = 25 + (lines_drawn * FONT_SMALL.get_linesize())
            if active_enemy.answer == "HOLD_SPACE":
                pygame.draw.rect(screen, BLACK, (135, dy_y + 10, 300, 20), 1)
                if space_hold_start_time > 0:
                    charge_pct = min((current_time - space_hold_start_time) / 1500, 1.0)
                    pygame.draw.rect(screen, GREEN, (137, dy_y + 12, int(296 * charge_pct), 16))
            else:
                screen.blit(FONT_MED.render(f"Your Answer: {player_input}", True, GREEN), (35, min(dy_y, 110)))

    elif game_state == "VICTORY":
        accuracy_pct = (correct_attempts / total_attempts) * 100 if total_attempts > 0 else 0
        score_surface = FONT_MED.render(f"Final Score: {score}", True, BLACK)
        accuracy_surface = FONT_MED.render(f"Typing Accuracy: {round(accuracy_pct, 1)}%", True, BLACK)
        exit_surface = FONT_MED.render("Press [SPACEBAR] to exit the game.", True, TEXT_MUTED)
        win_surface = FONT_TITLE.render("Session Cleared Successfully.", True, GREEN)
        info_surface = FONT_MED.render("Data streamed live to your shared Google Form Sheet.", True, BLACK)
        remind_surface = FONT_SMALL.render(f"Logged for reminders: {player_email}", True, TEXT_MUTED)
        screen.blit(win_surface, (150, 220))
        screen.blit(info_surface, (160, 270))
        screen.blit(remind_surface, (170, 330))
        screen.blit(score_surface, (200,250))
        screen.blit(accuracy_surface, (200, 290))
        screen.blit(exit_surface, (200, 360))

        if pygame.key.get_pressed()[pygame.K_SPACE]:
            running = False


    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
