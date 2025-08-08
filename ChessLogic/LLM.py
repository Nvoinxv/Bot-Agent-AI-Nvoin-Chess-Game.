from dotenv import load_dotenv
import os
from chess import Board
from google.generativeai import GenerativeModel
import google.generativeai as genai
import re
import chess
import time
import random

load_dotenv()
genai_api_key = os.getenv("API_KEY_GEMINI")

genai.configure(api_key=genai_api_key)

# Optimisasi Konfigurasi untuk speed
# Dan juga biar mempercepat pemrosesan
generation_config = {
    "temperature": 0.7,  
    "top_p": 0.8,
    "top_k": 50,
    "max_output_tokens": 50,  
    "candidate_count": 1
}

# Safety settings untuk mengurangi blocking
# Soal nya gemini itu terlalu ketat cuy
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel("gemini-2.0-flash-exp", 
                             generation_config=generation_config,
                             safety_settings=safety_settings)

# Ini sebenarnya buat Uji aja tapi tetap nanti akan di gabung yakan
def system_prompt_elo(user_prompt):
    """System prompt yang lebih ringkas untuk speed"""
    return f"""
CHESS AI - ELO 1600 LEVEL

STYLE:
- Play as an attacking player who adapts the strategy based on the position.
- Sometimes play sharp tactical lines, sometimes positional pressure.
- Mix strategies so the opponent cannot predict the next move.
- Always look for checkmate patterns first if possible.
- Avoid pushing too many pawns early unless part of an attack.
- Maintain good piece activity and king safety.

RULES:
- Output only chess move in algebraic notation.
- Examples: Nf3, e4, O-O, Bxf7+, Qh5#, Nc6.
- Decision priority:
    1. Immediate checkmate or forced mate sequences.
    2. Checks and forcing moves.
    3. Captures, especially of high-value pieces.
    4. Piece development and control of key squares.
    5. Strategic pawn moves supporting an attack.
- Vary approach: sometimes go for direct attacks, sometimes build pressure.
- No explanations, just the move.

POSITION ANALYSIS:
{user_prompt}

Move:"""

# Ini emoji catur yang di gunakan
chess_pieces_emoji = {
    'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚', 'p': '♟',  # Black
    'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔', 'P': '♙',  # White
    '.': '·'  
}

# Membuat papan catur dengan emoji yang kita sudah buat tadi.
def board_to_emoji(board):
    """Convert chess board to emoji representation"""
    board_str = str(board)
    lines = board_str.split('\n')
    
    emoji_lines = []
    for i, line in enumerate(lines):
        emoji_line = ""
        rank_num = 8 - i
        emoji_line += f"{rank_num} "
        
        for char in line.split():
            if char in chess_pieces_emoji:
                emoji_line += chess_pieces_emoji[char] + " "
            else:
                emoji_line += "· "
        
        emoji_lines.append(emoji_line)
    
    emoji_lines.append("  a b c d e f g h")
    
    return '\n'.join(emoji_lines)

# Lalu tambahkan emoji catur di setiap posisi
def tambahkan_emoji_catur(teks):
    """Tambahkan emoji catur ke teks - OPTIMIZED"""
    quick_replacements = {
        "check": "☑️", "mate": "♚💀", "checkmate": "♚💀",
        "White": "⚪", "Black": "⚫", "white": "⚪", "black": "⚫",
        "wins": "🏆", "draw": "🤝", "victory": "🎉"
    }
    
    for kata, emoji in quick_replacements.items():
        teks = teks.replace(kata, emoji)
    
    return teks

# Membuat catur untuk bagian discord nya
def prompt_discord_gameplay_fast(fen, warna):
    """Ultra-fast prompt untuk speed chess dengan instruksi gaya dan aturan"""
    return f"""
You are a chess engine playing as {warna.upper()}.

STYLE:
- Play aggressively but adapt your strategy based on the position.
- Mix sharp tactical attacks with positional pressure.
- Be unpredictable to your opponent.
- Always prioritize immediate checkmate or forced mate sequences.
- Avoid pushing too many pawns early unless part of an attack.
- Maintain good piece activity and king safety.

RULES:
- Output only one chess move in standard algebraic notation.
- Examples: Nf3, e4, O-O, Bxf7+, Qh5#, Nc6.
- Decision priorities:
    1. Immediate checkmate or forced mate.
    2. Checks and forcing moves.
    3. Captures, especially of high-value pieces.
    4. Development and control of key squares.
    5. Strategic pawn moves supporting attacks.
- Vary your approach: sometimes direct attacks, sometimes build positional pressure.
- No explanations or commentary, only the move.

Current board position (FEN): {fen}

Your move:
"""

# Mempercepat game catur dengan prompt
# Biasa nya kan kalau pakai LLM kek gemini lambat
# Jadi kita buat fungsi ini, ya walaupun udah ada optimisasi.
def extract_move_from_response_fast(response_text):
    """OPTIMIZED extraction untuk speed"""
    if not response_text:
        return None
    
    response_text = response_text.strip()
    move_pattern = r'\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O-?O?)\b'
    matches = re.findall(move_pattern, response_text)
    
    if matches:
        for move in matches:
            if len(move) >= 2:
                return move.replace('0', 'O')
    
    return None

def get_safe_fallback_move(board, warna):
    """Get aggressive fallback move untuk gaya ELO 1600"""
    legal_moves = list(board.legal_moves)
    legal_sans = [board.san(move) for move in legal_moves]
    
    if not legal_sans:
        return None

    # Agresif: prioritaskan skakmat, serangan, capture besar
    priority_moves = [
        [m for m in legal_sans if '#' in m],  # Checkmate langsung
        [m for m in legal_sans if '+' in m],  # Skak
        [m for m in legal_sans if 'x' in m and any(p in m for p in ['Q','R','B','N'])],  # Tangkap bidak besar
        [m for m in legal_sans if 'x' in m],  # Tangkap apapun
        [m for m in legal_sans if any(p in m for p in ['Q','R','B','N'])],  # Pengembangan & serangan
        [m for m in legal_sans if m in ['e4','d4','e5','d5']],  # Kontrol center
        [m for m in legal_sans if m in ['O-O', 'O-O-O']],  # Rokade
        [m for m in legal_sans if m[0] in 'abcdefgh'],  # Pawn moves terakhir
        legal_sans  # fallback
    ]

    for moves in priority_moves:
        if moves:
            return random.choice(moves)

    return legal_sans[0]

def bot_instruction_fast(fen, warna):
    """OPTIMIZED bot instruction dengan error handling untuk Gemini"""
    try:
        start_time = time.time()
        
        prompt = prompt_discord_gameplay_fast(fen, warna)
        full_prompt = system_prompt_elo(f"Playing as: {warna}\n{prompt}")
        response = model.generate_content(full_prompt)
        
        elapsed = time.time() - start_time
        print(f"⚡ AI response time: {elapsed:.2f}s")
        
        # Check if response is valid and has content
        if (response and hasattr(response, 'candidates') and response.candidates and 
            response.candidates[0].content and response.candidates[0].content.parts):
            
            return response.text if response.text else ""
        else:
            # Handle blocked/empty response
            print("⚠️ API response blocked by safety filters, using fallback")
            return ""
            
    except Exception as e:
        print(f"❌ Gemini API Error: {str(e)}")
        if "finish_reason" in str(e) and "2" in str(e):
            print("🛡️ Content blocked by safety filter")
        return ""

def get_quick_move_fast(fen, warna):
    try:
        temp_board = Board(fen)
        legal_moves = list(temp_board.legal_moves)
        legal_sans = [temp_board.san(move) for move in legal_moves]

        if not legal_moves:
            return None, "No legal moves available"

        print(f"⚡ Thinking as {warna}...")

        # Dapat response AI
        response = bot_instruction_fast(fen, warna)

        if response:
            move = extract_move_from_response_fast(response)
            if move:
                try:
                    move_obj = temp_board.parse_san(move)
                    if move_obj in temp_board.legal_moves:
                        return move, "🚀 Langkah AI_AGENT_NVOIN"
                    else:
                        print(f"⚠️ AI_AGENT_NVOIN sugesti melakukan langkah illegal: {move}")
                except Exception as e:
                    print(f"⚠️ AI_AGENT_NVOIN sugesti tidak valid: {move} ({str(e)})")

        # Kalau AI_AGENT_NVON INI gagal kasih langkah legal, mundur ke smart move
        print("🤖 Gunakan AI_AGENT_NVOIN untuk Mundur...")
        fallback_move = get_safe_fallback_move(temp_board, warna)
        if fallback_move:
            return fallback_move, "⚡ Mundur yang Pintar"
        else:
            return random.choice(legal_sans), "🎲 Mundur acak"

    except Exception as e:
        print(f"❌ Berkritis error: {str(e)}")
        try:
            temp_board = Board(fen)
            legal_moves = list(temp_board.legal_moves)
            if legal_moves:
                legal_sans = [temp_board.san(move) for move in legal_moves]
                return random.choice(legal_sans), "🆘 Emergency fallback"
        except:
            pass
        return None, f"💥 Fatal error: {str(e)}"

def bot_instruction(fen, bot_color):
    """Wrapper function untuk Discord bot compatibility"""
    move, reasoning = get_quick_move_fast(fen, bot_color)
    return f"{reasoning}: {move}" if move else "Error generating move"

def extract_move_from_response(response_text):
    """Wrapper function untuk Discord bot compatibility"""
    if ":" in response_text:
        move_part = response_text.split(":")[-1].strip()
        return extract_move_from_response_fast(move_part)
    else:
        return extract_move_from_response_fast(response_text)

# Mengevaluasi atau penilaian agresif AGENT AI NVOIN gw
# Biar gak asal asalan langkah tapi juga gak terlalu konservatif
def get_aggressive_fallback_move(board, warna):
    """Fallback move dengan penilaian agresif ala ELO 1600"""
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None
    
    best_move = None
    best_score = -9999

    # Nilai bidak standar
    piece_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9}

    for move in legal_moves:
        score = 0
        san = board.san(move)

        # Checkmate langsung
        if "#" in san:
            score += 1000

        # Skak
        if "+" in san:
            score += 50

        # Capture bidak
        if "x" in san:
            target_square = move.to_square
            target_piece = board.piece_at(target_square)
            if target_piece:
                score += piece_values.get(target_piece.symbol().lower(), 0) * 10

        # Kontrol center
        center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]
        if move.to_square in center_squares:
            score += 15

        # Pengembangan bidak utama (hindari pawn spam)
        if board.piece_at(move.from_square).symbol().lower() in ["n", "b", "q", "r"]:
            score += 10

        # Rokade
        if san in ["O-O", "O-O-O"]:
            score += 20

        # Simpan langkah terbaik
        if score > best_score:
            best_score = score
            best_move = move

    return board.san(best_move)

def user_input_move_fast():
    """Fast user input dengan emoji"""
    print("⚡ Lu berbalik! Pilih langkah gacor lu (e4, Nf3, O-O):")
    move = input("🎯 >> ").strip()
    return move if move else user_input_move_fast()

def display_game_status(board, move_counter, giliran, warna_user, warna_bot):
    """Enhanced display dengan emoji"""
    print("\n" + "="*50)
    print(f"🎮 Langkah {move_counter} | Turn: {'⚪' if giliran == 'white' else '⚫'}")
    print(f"👤 Kamu: {warna_user} | 🤖 AI_AGENT_NVOIN: {warna_bot}")
    print("="*50)
    
    # Emoji board
    print(board_to_emoji(board))
    
    # Quick status
    if board.is_check():
        print("☑️ CHECK!")
    
    print(f"📍 FEN: {board.fen()[:30]}...")

# Rangkaian Utama permaianan setelah buat fungsi
def main_game_loop():
    """OPTIMIZED game loop dengan emoji UI"""
    board = Board()

    # UI dengan emoji untuk pilih warna
    print("🎮 AI_AGENT_NVOIN Chess game!")
    print()
    print("⚪ Bagian putih: ♔♕♖♗♘♙")  
    print("⚫ Bagian hitam: ♚♛♜♝♞♟")
    print()
    
    pilihan_warna = input("🎯 Pilih warna (⚪ putih / ⚫ hitam): ").strip().lower()
    if pilihan_warna in ["white", "putih", "w", "⚪"]:
        warna_user = "white"
        warna_bot = "black"
        print("⚪ Kamu bermain sebagai putih | 🤖 AI_AGENT_NVOIN bermain sebagai hitam")
    else:
        warna_user = "black" 
        warna_bot = "white"
        print("⚫ Kamu bermain sebagai hitam | 🤖 AI_AGENT_BOT bermain sebagai putih")

    giliran = "white"
    move_counter = 0
    game_start = time.time()

    while not board.is_game_over():
        move_counter += 1
        move_start = time.time()
        
        display_game_status(board, move_counter, giliran, warna_user, warna_bot)

        if giliran == warna_bot:
            print(f"🤖 AI_AGENT_NVOIN melangkah ({warna_bot})...")
            
            bot_move, bot_reasoning = get_quick_move_fast(board.fen(), warna_bot)
            
            if bot_move:
                try:
                    move_obj = board.parse_san(bot_move)
                    if move_obj in board.legal_moves:
                        board.push(move_obj)
                        
                        move_time = time.time() - move_start
                        print(f"🤖 Bot plays: {bot_move} ⚡ ({move_time:.1f}s)")
                        print(f"💭 {bot_reasoning}")
                        
                        # Show immediate effect
                        if board.is_check():
                            print("☑️ CHECK!")
                        if '+' in bot_move:
                            print("⚔️ Langkah Aggressive!")
                    else:
                        print(f"❌ Illegal: {bot_move}")
                        break
                except Exception as e:
                    print(f"⚠️ Parse error: {e}")
                    break
            else:
                print("❌ Bot gagal!")
                break
                
        else:
            print(f"👤 Your turn ({warna_user})...")
            user_move = user_input_move_fast()
            
            try:
                move_obj = board.parse_san(user_move)
                if move_obj in board.legal_moves:
                    board.push(move_obj)
                    
                    move_time = time.time() - move_start
                    print(f"✅ You played: {user_move} ⚡ ({move_time:.1f}s)")
                    
                    # Show effect
                    if board.is_check():
                        print("☑️ CHECK!")
                else:
                    print(f"🚫 Illegal: {user_move}")
                    available = [board.san(m) for m in list(board.legal_moves)[:5]]
                    print(f"💡 Try: {', '.join(available)}...")
                    continue
            except Exception as e:
                print(f"⚠️ Tidak valid: {e}")
                print("💡 Format: e4, Nf3, O-O, Qxd4")
                continue

        giliran = "black" if giliran == "white" else "white"

    # GAME OVER dengan emoji
    # Disitu gw tambahin siapa yang menang
    game_time = time.time() - game_start
    print("\n" + "🏁"*20)
    print("GAME OVER!")
    print("🏁"*20)
    
    print("📊 posisi final nya:")
    print(board_to_emoji(board))
    
    result = board.result()
    if result == "1-0":
        winner = "⚪ Putih menang! 🏆"
    elif result == "0-1":
        winner = "⚫ Hitam menang! 🏆"  
    else:
        winner = "🤝 Salaman dulu biar deal meang!"
    
    print(f"\n🏆 Hasil: {result}")
    print(f"🎉 {winner}")
    
    # Stats Game
    print(f"\n📈 Game Stats:")
    print(f"⏱️ Total waktu: {game_time:.1f}s")
    print(f"🎯 Total langka: {move_counter}")
    print(f"⚡ Rata rata per langkah: {game_time/move_counter:.1f}s")
    
    # Ending reason dengan emoji
    if board.is_checkmate():
        print("🎯 Reason: CHECKMATE! ♚💀")
    elif board.is_stalemate():
        print("😐 Reason: Stalemate")
    elif board.is_insufficient_material():
        print("♟️ Reason: Insufficient material")
    elif board.is_seventyfive_moves():
        print("📏 Reason: 75-move rule")
    elif board.is_fivefold_repetition():
        print("🔄 Reason: Repetition")

# Uji kecepatan bot berposisis
def test_bot_speed():
    """Test bot speed untuk berbagai posisi"""
    test_positions = [
        ("Starting", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
        ("Middle game", "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 4"),
        ("Endgame", "8/8/8/3k4/8/3K4/8/R7 w - - 0 1")
    ]
    
    print("🧪 SPEED TEST")
    print("="*30)
    
    total_time = 0
    for name, fen in test_positions:
        print(f"\n🎯 Testing {name}...")
        start = time.time()
        
        move, reason = get_quick_move_fast(fen, "white")
        
        elapsed = time.time() - start
        total_time += elapsed
        
        print(f"⚡ Time: {elapsed:.2f}s | Move: {move}")
    
    print(f"\n📊 Average speed: {total_time/len(test_positions):.2f}s per move")
    print("🚀 Speed test complete!")

# Buat Main Loop Jika mau Uji Bot 
# Kalau mau  coba coba yakan
if __name__ == "__main__":
    print("🎮 FAST CHESS AI BOT ELO 1600")
    print("⚡ AGGRESSIVE EDITION - SPEED OPTIMIZED")
    print("🎯 Perfect for blitz games (3+0, 5+0, 8+0)")
    print()
    print("🔥 Features:")
    print("   ⚡ Ultra-fast move generation (<2s)")
    print("   🎨 Full emoji UI")  
    print("   ⚔️ Aggressive tactical play")
    print("   📊 Game statistics")
    print()
    print("Choose mode:")
    print("1. 🎯 Play game")
    print("2. 🧪 Test bot position")
    print("3. ⚡ Speed test")
    
    pilihan = input("👉 Select (1/2/3): ").strip()

    if pilihan == "1":
        main_game_loop()
    elif pilihan == "2":
        print("🧪 Position test:")
        test_fen = input("FEN (or Enter for start): ").strip()
        if not test_fen:
            test_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        test_color = input("Bot color (white/black): ").strip().lower()
        if test_color not in ["white", "black"]:
            test_color = "white"
            
        print(f"🧪 Testing bot as {test_color}...")
        start_time = time.time()
        move, reasoning = get_quick_move_fast(test_fen, test_color)
        test_time = time.time() - start_time
        
        print(f"🎯 Bot move: {move}")
        print(f"💭 Reasoning: {reasoning}")
        print(f"⚡ Time: {test_time:.2f}s")
    elif pilihan == "3":
        test_bot_speed()
    else:
        print("❌ Invalid choice!")