import discord
from discord.ext import commands, tasks
import asyncio
import random
import time
from datetime import datetime, timedelta
import LLM
import os
from chess import Board
from dotenv import load_dotenv

load_dotenv()
TOKEN_DISCORD = os.getenv("API_KEY_DISCORD")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Storage untuk game sessions
game_sessions = {}

# Konstanta game
GAME_DURATION = 600  
CHECK_INTERVAL = 30  

# Kelas permainan catur untuk discord bot
# Beda nya di file BotDiscordChess.py dan LLM.py
# Kalau ini bagian implementasi untuk discord bot 
# Sedangkan di llm.py itu mengatur LLM nya dan juga gw tambahkan uji testing nya.
class ChessGame:
    def __init__(self, user_id, user_color, bot_color):
        # Penamaan variabel ini penting diisi.
        self.user_id = user_id
        self.user_color = user_color
        self.bot_color = bot_color
        self.current_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        self.move_number = 1
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(seconds=GAME_DURATION)
        self.moves_history = []
        self.waiting_for_user = False
        
    def get_current_turn(self):
        """Menentukan giliran berdasarkan FEN"""
        return self.current_fen.split()[1] 
    
    def is_user_turn(self):
        """Check apakah giliran user"""
        current_turn = self.get_current_turn()
        return (current_turn == 'w' and self.user_color == 'white') or \
               (current_turn == 'b' and self.user_color == 'black')
    
    def is_game_expired(self):
        """Check apakah game sudah expired"""
        return datetime.now() > self.end_time
    
    def get_remaining_time(self):
        """Get waktu yang tersisa"""
        remaining = self.end_time - datetime.now()
        return max(0, int(remaining.total_seconds()))
    
    def add_move(self, move, player):
        """Tambah move ke history"""
        self.moves_history.append({
            'move': move,
            'player': player,
            'time': datetime.now(),
            'move_number': self.move_number
        })
        
        # Update move number setelah hitam main
        if self.get_current_turn() == 'w':
            self.move_number += 1

def fen_to_board_display(fen):
    """Convert FEN string ke visual board dengan Unicode chess pieces"""
    # Mapping FEN ke board display atau UI nya di Discord
    piece_symbols = {
        'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚', 'p': '♟',  # Black pieces
        'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔', 'P': '♙'   # White pieces
    }
    
    # Parse FEN untuk mendapatkan board position
    board_fen = fen.split()[0]
    rows = board_fen.split('/')
    
    board_display = "```\n"
    board_display += "  a b c d e f g h\n"
    
    for i, row in enumerate(rows):
        rank = 8 - i
        board_display += f"{rank} "
        
        for char in row:
            if char.isdigit():
                # Empty squares
                for _ in range(int(char)):
                    board_display += "· "
            else:
                # Piece
                board_display += piece_symbols.get(char, '?') + " "
        
        board_display += f"{rank}\n"
    
    board_display += "  a b c d e f g h\n"
    board_display += "```"
    
    return board_display

def format_time(seconds):
    """Format waktu ke mm:ss"""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

# Bagian sini mengatur permainan biar keliatan bagus.
def create_game_embed(game, title, description="", color=discord.Color.blue()):
    """Buat embed untuk game info"""
    embed = discord.Embed(title=title, description=description, color=color)
    
    # Menambahkan chess board
    board_display = fen_to_board_display(game.current_fen)
    embed.add_field(name="🏁 Posisi saat ini", value=board_display, inline=False)
    
    # Info game
    user_emoji = "⚪" if game.user_color == "white" else "⚫"
    bot_emoji = "⚫" if game.user_color == "white" else "⚪"
    
    embed.add_field(
        name="🎮 Pemain",
        value=f"{user_emoji} Kamu: {game.user_color.upper()}\n{bot_emoji} AI AGENT NVOIN CHESS: {game.bot_color.upper()}",
        inline=True
    )
    
    remaining_time = game.get_remaining_time()
    embed.add_field(
        name="⏰ Waktu permainan",
        value=f"`{format_time(remaining_time)}`",
        inline=True
    )
    
    embed.add_field(
        name="🎯 Move Number",
        value=f"`{game.move_number}`",
        inline=True
    )
    
    # Current turn
    current_turn = "You" if game.is_user_turn() else "Bot"
    turn_emoji = user_emoji if game.is_user_turn() else bot_emoji
    embed.add_field(
        name="👤 Current Turn",
        value=f"{turn_emoji} {current_turn}",
        inline=True
    )
    
    if game.moves_history:
        recent_moves = game.moves_history[-5:]
        moves_text = ""
        for move_data in recent_moves:
            player_emoji = user_emoji if move_data['player'] == 'user' else bot_emoji
            moves_text += f"{player_emoji} `{move_data['move']}` "
        
        embed.add_field(
            name="📝 Menerima kembali langkah",
            value=moves_text or "Tidak ada langkah",
            inline=False
        )
    
    embed.add_field(
        name="🔧 Komen",
        value="`!move_chess <your_move>` - bikin anda melangkah dari permainan catur\n`!status_chess` - Cek status game\n`!quit_chess` - Game berakhir.",
        inline=False
    )
    
    embed.set_footer(text=f"FEN: {game.current_fen[:50]}{'...' if len(game.current_fen) > 50 else ''}")
    
    return embed

@bot.event
async def on_ready():
    print(f"♟️ Chess Bot sudah login sebagai {bot.user}")
    print("🎮 Bot siap melayani permainan catur!")
    cleanup_expired_games.start()

@tasks.loop(seconds=CHECK_INTERVAL)
async def cleanup_expired_games():
    """Background task untuk cleanup expired games"""
    expired_users = []
    
    for user_id, game in game_sessions.items():
        if game.is_game_expired():
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del game_sessions[user_id]
        print(f"⏰ Game expired untuk user {user_id}")

# Bagian sini adalah memulai untuk permainan catur
# Dimana kalau di discord lu panggil !start_chess
@bot.command(name="start_chess")
async def start_chess(ctx, warna: str = "random"):
    user_id = ctx.author.id

    if user_id in game_sessions:
        game = game_sessions[user_id]
        if not game.is_game_expired():
            remaining = game.get_remaining_time()
            embed = create_game_embed(
                game, 
                "🚫 Game Sudah aktif tadi!", 
                f"Lu sudah aktifin game nya tadi dan gak keluar dari game tersebut!\nRemaining time: `{format_time(remaining)}`\nUse `!quit_chess` to end current game.",
                discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        else:
            del game_sessions[user_id]
    
    if warna == "random":
        warna = random.choice(["putih", "hitam"])
    
    if warna == "putih":
        user_color = "white"
        bot_color = "black"
    else:
        user_color = "black"
        bot_color = "white"

    game = ChessGame(user_id, user_color, bot_color)
    game_sessions[user_id] = game
    embed = create_game_embed(
        game,
        "♟️ Chess Game Started!",
        f"🎮 New chess game has been created!\n⏰ Game will last **10 minutes**\n\n**Good luck and have fun!** 🍀"
    )
    
    await ctx.send(embed=embed)
    if not game.is_user_turn():
        await asyncio.sleep(2)
        await make_bot_move(ctx, game)

async def make_bot_move(ctx, game):
    try:
        thinking_embed = discord.Embed(
            title="🤖 Nvoin AI Agent Chess Bot...",
            description="🤔 Analisis posisi tergacor...",
            color=discord.Color.yellow()
        )
        thinking_msg = await ctx.send(embed=thinking_embed)
        
        bot_move, reason = LLM.get_quick_move_fast(game.current_fen, game.bot_color)
        
        await thinking_msg.delete()
        
        if bot_move:
            # Validasi dan update posisi
            board = Board(game.current_fen)
            move_obj = board.parse_san(bot_move)
            if move_obj in board.legal_moves:
                board.push(move_obj)
                game.current_fen = board.fen()  # Update posisi game
                game.add_move(bot_move, 'bot')
                game.waiting_for_user = True  # Giliran user sekarang
                
                embed = create_game_embed(
                    game,
                    "🤖 AI AGENT NVOIN CHESS MAJU",
                    f"Bot played: **`{bot_move}`**"
                )
                embed.add_field(
                    name="🧠 AI AGENT NVOIN CHESS Analisis",
                    value=f"```{reason}```",
                    inline=False
                )
                embed.add_field(
                    name="👤 Giliran lu!",
                    value="Gunakan `!move_chess <your_move>` agar bisa melangkah di game catur.",
                    inline=False
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ AI AGENT NVOIN CHESS  melakukan langkah illegal, game berakhir.")
                del game_sessions[ctx.author.id]
        else:
            await ctx.send("❌ AI AGENT NVOIN CHESS  gagal generate langkah, game berakhir")
            del game_sessions[ctx.author.id]
            
    except Exception as e:
        await ctx.send(f"❌ Error selama AI AGENT NVOIN CHESS melangkah: {str(e)}")
        del game_sessions[ctx.author.id]

# Setelah lu melakukan !start_chess maka untuk memainkan nya
# Lu perlu mainkan seperti !move_chess e4 atau !move_chess Nf3 dan seterus nya 
# inti nya lu perlu ngirim perintah !move_chess <posisi>
@bot.command(name="move_chess")
async def make_move(ctx, *, move: str):
    user_id = ctx.author.id
    
    # Check game exists
    if user_id not in game_sessions:
        embed = discord.Embed(
            title="❌ Game tidak aktif",
            description="Game gak akan aktif, lakukan !start_chess putih, !start_chess hitam, atau !start_chess random",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    game = game_sessions[user_id]
    
    # Check game expired
    if game.is_game_expired():
        embed = discord.Embed(
            title="⏰ Game Kadulwarsa",
            description="Game sudah berakhir, sudah melewati 10 menit.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        del game_sessions[user_id]
        return
    
    if not game.is_user_turn():
        embed = discord.Embed(
            title="❌ Jangan langkah dulu sebagai user",
            description="Tunggu bot berpikir untuk melangkah!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    move = move.strip()
    if not move:
        embed = discord.Embed(
            title="❌ Langkah tidak valid",
            description="Tolong berikan langkah yang valid! (e.g., e4, Nf3, O-O)",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    # Validasi move user dulu di sini
    try:
        board = Board(game.current_fen)
        move_obj = board.parse_san(move)  # parse move dari SAN
        if move_obj not in board.legal_moves:
            raise ValueError("langkah illegal")

        # Jika valid, push move ke board dan update FEN game
        board.push(move_obj)
        game.current_fen = board.fen()  # update posisi game

        # Tambahkan move ke history game
        game.add_move(move, 'user')
        game.waiting_for_user = False
        
        embed = create_game_embed(
            game,
            "✅ Langkah di terima",
            f"You played: **`{move}`**\n\n🤖 Nvoin Agent Bot Chess Berpikir..."
        )
        await ctx.send(embed=embed)
        await asyncio.sleep(1)
        await make_bot_move(ctx, game)

    except Exception as e:
        embed = discord.Embed(
            title="❌ Langkah yang tidak valid",
            description=f"Langkah `{move}` adalah ilegal atau tidak valid.\nMohon gunakan langkah yang legal.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# Mengecek status catur juga sama lu perlu !status_chess
# Biasa nya bagian status catur cuma mengecek status dari permainan selama lu main catur tersebut.
@bot.command(name="status_chess")
async def game_status(ctx):
    user_id = ctx.author.id
    
    if user_id not in game_sessions:
        embed = discord.Embed(
            title="❌ Game tidak aktif.",
            description="Lu perlu aktifin game baru bisa cek status catur dari game catur.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    game = game_sessions[user_id]
    
    if game.is_game_expired():
        embed = discord.Embed(
            title="⏰ Game Kadulwarsa",
            description="Game berakhir udah batas 10 menit.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        del game_sessions[user_id]
        return
    
    embed = create_game_embed(game, "📊 Game Status")
    await ctx.send(embed=embed)

# Bagian sini adalah quit dari game catur 
# kalau lu ketik perintah !quit_chess maka otomatis keluar dari permainan.
@bot.command(name="quit_chess")
async def quit_game(ctx):
    user_id = ctx.author.id
    
    if user_id not in game_sessions:
        embed = discord.Embed(
            title="❌ Game tidak aktif.",
            description="Lu perlu aktifin game baru bisa keluar dari game catur.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    game = game_sessions[user_id]
    
    # Membuat ringkasan permainan
    total_moves = len(game.moves_history)
    duration = datetime.now() - game.start_time
    duration_str = f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"
    
    embed = discord.Embed(
        title="🚪 Game Berakhir",
        description="Kamu keluar dari game.",
        color=discord.Color.orange()
    )
    
    embed.add_field(name="📊 Ringkasan game", value=f"Total langkah: `{total_moves}`\nDurasi: `{duration_str}`", inline=False)
    
    if game.moves_history:
        last_moves = game.moves_history[-3:]
        moves_text = ""
        for move_data in last_moves:
            player = "You" if move_data['player'] == 'user' else "Bot"
            moves_text += f"{player}: `{move_data['move']}`\n"
        embed.add_field(name="📝 Langkah terakhir", value=moves_text, inline=False)
    
    embed.add_field(name="🎮 Play Again?", value="Use `!start_chess` to begin a new game!", inline=False)
    
    await ctx.send(embed=embed)
    del game_sessions[user_id]

# Ini adalah info buat lu yang gak ngerti gameplay catur buatan gw
# ketik !help_chess maka keluar seperti ini.
@bot.command(name="help_chess")
async def help_command(ctx):
    embed = discord.Embed(
        title="♟️ Chess Bot Help",
        description="Selamat datang di Chess Bot AI Nvoin. Disini panduan untuk anda bermain catur: ",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎮 Basic Commands",
        value="`!start_chess [color]` - Memulai permainan catur\n`!move_chess <move>` - Untuk melangkah\n`!status_chess` - Cek status game catur\n`!quit_chess` - Keluar dari game catur.",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Move Format",
        value="Gunakan standar notasi catur seperti ini:\n• `e4`, `d4` - Pergerakan pion\n• `Nf3`, `Bc4` - Gerakan potongan\n• `O-O` - Sisi raja\n• `O-O-O` - Sisi ratu",
        inline=False
    )
    
    embed.add_field(
        name="🎨 Color Options",
        value="`!start_chess putih` - Bermain sebagai catur putih\n`!start_chess hitam` - Bermain sebagai catur hitam\n`!start_chess random` - maka di acak atau di tentukan oleh bot.",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Game Rules",
        value="• Setiap akhir permainan **10 minutes**\n• Pilih hitam, putih, atau random\n• Agent Bot nya itu sekitar ~1000 - ~1300 ELO.\n• Gunakan notasi catur biar bisa di mainkan saat melangkah.",
        inline=False
    )
    
    embed.add_field(
        name="🤖 About the Bot",
        value="Nvoin Bot Agent AI ini menggunakan LLM yaitu gemini.",
        inline=False
    )
    
    embed.set_footer(text="Semoga jago dan beruntung menang! ♟️")
    
    await ctx.send(embed=embed)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ Cooldown",
            description=f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
            color=discord.Color.red()
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Argument",
            description=f"Missing required argument: `{error.param.name}`",
            color=discord.Color.red()
        )
    else:
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(error)}",
            color=discord.Color.red()
        )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(TOKEN_DISCORD)