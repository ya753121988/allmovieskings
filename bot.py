import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_secure_key_99"

# --- কনফিগারেশন (আপনার তথ্য দিন) ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['movie_premium_db']
movies_col = db['content']
settings_col = db['site_settings']
cat_col = db['categories']

# ডিফল্ট সেটিংস সেটআপ
if not settings_col.find_one({"id": "main"}):
    settings_col.insert_one({
        "id": "main",
        "site_name": "MOVIE-PLEX",
        "site_logo": "https://i.ibb.co/logo.png",
        "header_notice": "আমাদের সাইটে স্বাগতম! নতুন মুভি ও সিরিজ উপভোগ করুন।",
        "movie_limit": 10,
        "series_limit": 10,
        "ep_limit": 10,
        "admin_user": "admin",
        "admin_pass": "1234"
    })

# --- CSS & JS (Premium UI) ---
UI_HEADER = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --primary: #e50914; --bg: #06090f; --glass: rgba(255,255,255,0.05); }
    body { background: var(--bg); color: white; font-family: 'Poppins', sans-serif; }
    .glass { background: var(--glass); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
    .card-hover:hover { transform: scale(1.05); transition: 0.4s ease; z-index: 10; }
    .sidebar { transition: 0.3s; }
    .active-nav { border-left: 4px solid var(--primary); background: rgba(229, 9, 20, 0.1); }
</style>
"""

# --- ১. ইউজার হোমপেজ টেমপ্লেট ---
HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    <!-- Navbar -->
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <div class="flex items-center gap-4">
            <button onclick="toggleMenu()" class="text-2xl"><i class="fa fa-bars"></i></button>
            <h1 class="text-2xl font-black text-red-600">{{ conf.site_name }}</h1>
        </div>
        <form action="/" method="GET" class="hidden md:flex bg-gray-800 rounded-full px-4 py-1 items-center">
            <input name="s" placeholder="Search..." class="bg-transparent outline-none p-1 w-64">
            <button type="submit"><i class="fa fa-search"></i></button>
        </form>
    </nav>

    <!-- Side Menu (3-Dot Alternative) -->
    <div id="sideMenu" class="fixed left-[-300px] top-0 h-full w-[250px] glass z-[60] sidebar p-6">
        <button onclick="toggleMenu()" class="mb-10 text-xl"><i class="fa fa-times"></i> Close</button>
        <div class="grid gap-6 font-bold">
            <a href="/"><i class="fa fa-home"></i> Home</a>
            {% for c in cats %}<a href="/category/{{ c.name }}">{{ c.name }}</a>{% endfor %}
            <a href="/admin/login" class="text-gray-500 text-sm mt-10">Admin Login</a>
        </div>
    </div>

    <!-- Notice -->
    <div class="bg-red-600 p-1 text-center text-xs overflow-hidden"><marquee>{{ conf.header_notice }}</marquee></div>

    <main class="p-4 md:px-16">
        <!-- Top Slider (Top 10) -->
        <h2 class="text-xl font-bold mb-4 mt-6">🔥 Top Trending</h2>
        <div class="flex gap-4 overflow-x-auto no-scrollbar mb-10">
            {% for m in slider %}
            <div class="min-w-[280px] h-[160px] relative rounded-xl overflow-hidden shadow-xl cursor-pointer" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover">
                <div class="absolute inset-0 bg-gradient-to-t from-black to-transparent p-4 flex flex-col justify-end">
                    <p class="font-bold">{{ m.title }}</p>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Movie Grid -->
        <h2 class="text-xl font-bold mb-6">Latest Content</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {% for m in contents %}
            <div class="card-hover cursor-pointer" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.poster }}" class="rounded-lg aspect-[2/3] object-cover shadow-lg">
                <div class="mt-2 text-sm font-bold truncate">{{ m.title }}</div>
                <div class="text-[10px] text-gray-400">{{ m.year }} | {{ m.lang }}</div>
            </div>
            {% endfor %}
        </div>
    </main>

    <script>
        function toggleMenu() {
            let m = document.getElementById('sideMenu');
            m.style.left = m.style.left === '0px' ? '-300px' : '0px';
        }
    </script>
</body>
</html>
"""

# --- ২. অ্যাডমিন প্যানেল টেমপ্লেট ---
ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Dashboard</title></head>
<body class="flex">
    <!-- Sidebar -->
    <div class="w-64 h-screen glass sticky top-0 p-6 hidden md:block">
        <h2 class="text-primary font-black text-2xl mb-10">CONTROL</h2>
        <nav class="grid gap-4 font-semibold text-gray-400">
            <a href="/admin" class="active-nav p-2 rounded text-white"><i class="fa fa-plus-circle"></i> Add Content</a>
            <a href="/admin/manage" class="p-2 hover:text-white"><i class="fa fa-edit"></i> Manage All</a>
            <a href="/admin/cats" class="p-2 hover:text-white"><i class="fa fa-list"></i> Categories</a>
            <a href="/admin/settings" class="p-2 hover:text-white"><i class="fa fa-cog"></i> Site Settings</a>
            <a href="/logout" class="mt-20 p-2 text-red-500"><i class="fa fa-sign-out"></i> Logout</a>
        </nav>
    </div>

    <div class="flex-1 p-6 md:p-10">
        <h2 class="text-2xl font-bold mb-10">Add New Content (Movie/Series)</h2>
        
        <div class="grid md:grid-cols-2 gap-10">
            <!-- Auto System -->
            <div class="glass p-6 rounded-2xl">
                <h3 class="text-lg font-bold mb-4 text-blue-400">System 1: Auto (TMDB ID)</h3>
                <form action="/admin/add/auto" method="POST" class="grid gap-4">
                    <input name="tmdb_id" placeholder="TMDB ID (e.g. 550)" class="bg-gray-800 p-3 rounded border border-gray-700" required>
                    <select name="type" class="bg-gray-800 p-3 rounded">
                        <option value="movie">Movie</option>
                        <option value="tv">TV Series</option>
                    </select>
                    <button class="bg-blue-600 py-3 rounded font-bold">Auto Fetch & Save</button>
                </form>
            </div>

            <!-- Manual System -->
            <div class="glass p-6 rounded-2xl">
                <h3 class="text-lg font-bold mb-4 text-green-400">System 2: Manual Add</h3>
                <form action="/admin/add/manual" method="POST" class="grid gap-4">
                    <input name="title" placeholder="Title" class="bg-gray-800 p-3 rounded border border-gray-700" required>
                    <input name="year" placeholder="Year" class="bg-gray-800 p-3 rounded border border-gray-700">
                    <input name="lang" placeholder="Language" class="bg-gray-800 p-3 rounded border border-gray-700">
                    <input name="poster" placeholder="Poster URL (Vertical)" class="bg-gray-800 p-3 rounded border border-gray-700">
                    <input name="backdrop" placeholder="Thumbnail URL (Horizontal)" class="bg-gray-800 p-3 rounded border border-gray-700">
                    <textarea name="story" placeholder="Storyline" class="bg-gray-800 p-3 rounded border border-gray-700"></textarea>
                    <button class="bg-green-600 py-3 rounded font-bold">Save Manually</button>
                </form>
            </div>
        </div>

        <!-- Episode & Link Section -->
        <div class="mt-10 glass p-6 rounded-2xl">
            <h3 class="text-lg font-bold mb-4">Add Links/Episodes (Unlimited)</h3>
            <form action="/admin/add/links" method="POST" class="grid md:grid-cols-4 gap-4">
                <select name="content_id" class="bg-gray-800 p-3 rounded col-span-1">
                    {% for m in all_m %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}
                </select>
                <input name="quality" placeholder="Quality (e.g. 720p / Ep-01)" class="bg-gray-800 p-3 rounded border border-gray-700">
                <input name="tg_link" placeholder="Telegram Link" class="bg-gray-800 p-3 rounded border border-gray-700">
                <input name="direct_link" placeholder="Direct Download Link" class="bg-gray-800 p-3 rounded border border-gray-700">
                <button class="bg-indigo-600 p-3 rounded font-bold">Add This Link</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

# --- ৩. রুটিং ও লজিক (The Backend) ---

@app.route('/')
def home():
    conf = settings_col.find_one({"id": "main"})
    search = request.args.get('s')
    if search:
        contents = list(movies_col.find({"title": {"$regex": search, "$options": "i"}}))
    else:
        contents = list(movies_col.find().sort("_id", -1))
    
    cats = list(cat_col.find())
    slider = list(movies_col.find().sort("views", -1).limit(int(conf['slider_limit'] if 'slider_limit' in conf else 10)))
    
    return render_template_string(HOME_HTML, ui=UI_HEADER, conf=conf, contents=contents, cats=cats, slider=slider)

# অ্যাডমিন লগইন লজিক
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('user')
        p = request.form.get('pass')
        conf = settings_col.find_one({"id": "main"})
        if u == conf['admin_user'] and p == conf['admin_pass']:
            session['admin'] = True
            return redirect('/admin')
    return '<body style="background:#000;color:#fff;padding:50px"><form method="POST"><h2>Admin Login</h2><input name="user" placeholder="User"><br><input name="pass" type="password"><br><button>Login</button></form></body>'

@app.route('/admin')
def admin_panel():
    if not session.get('admin'): return redirect('/admin/login')
    all_m = list(movies_col.find().sort("_id", -1))
    return render_template_string(ADMIN_HTML, ui=UI_HEADER, all_m=all_m)

# অটো অ্যাড সিস্টেম (TMDB)
@app.route('/admin/add/auto', methods=['POST'])
def add_auto():
    tmdb_id = request.form.get('tmdb_id')
    m_type = request.form.get('type')
    api_url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=images"
    
    data = requests.get(api_url).json()
    if 'id' not in data: return "Invalid TMDB ID"

    # লোগো বের করা
    logos = data.get('images', {}).get('logos', [])
    logo_path = logos[0]['file_path'] if logos else None

    movie_data = {
        "title": data.get("title") or data.get("name"),
        "lang": data.get("original_language", "EN").upper(),
        "year": (data.get("release_date") or data.get("first_air_date", "2024"))[:4],
        "story": data.get("overview"),
        "poster": f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}",
        "backdrop": f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}",
        "logo": f"https://image.tmdb.org/t/p/original{logo_path}" if logo_path else None,
        "type": m_type,
        "views": 0,
        "links": []
    }
    movies_col.insert_one(movie_data)
    return redirect('/admin')

# ম্যানুয়াল অ্যাড সিস্টেম
@app.route('/admin/add/manual', methods=['POST'])
def add_manual():
    movie_data = {
        "title": request.form.get("title"),
        "year": request.form.get("year"),
        "lang": request.form.get("lang"),
        "poster": request.form.get("poster"),
        "backdrop": request.form.get("backdrop"),
        "story": request.form.get("story"),
        "links": [], "views": 0
    }
    movies_col.insert_one(movie_data)
    return redirect('/admin')

# ডাউনলোড লিংক ও আনলিমিটেড ইপিসোড অ্যাড
@app.route('/admin/add/links', methods=['POST'])
def add_links():
    m_id = request.form.get('content_id')
    link_obj = {
        "quality": request.form.get('quality'),
        "tg": request.form.get('tg_link'),
        "direct": request.form.get('direct_link')
    }
    movies_col.update_one({"_id": ObjectId(m_id)}, {"$push": {"links": link_obj}})
    return redirect('/admin')

# সাইট সেটিংস আপডেট (নাম, লোগো, নোটিশ, লিমিট)
@app.route('/admin/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('admin'): return redirect('/admin/login')
    if request.method == 'POST':
        settings_col.update_one({"id": "main"}, {"$set": {
            "site_name": request.form.get('site_name'),
            "site_logo": request.form.get('site_logo'),
            "header_notice": request.form.get('header_notice'),
            "slider_limit": request.form.get('slider_limit')
        }})
        return redirect('/admin/settings')
    conf = settings_col.find_one({"id": "main"})
    return render_template_string("""
        {{ ui|safe }}
        <div class="p-10 max-w-2xl mx-auto glass rounded-xl mt-10">
            <h2 class="text-2xl font-bold mb-6">⚙️ Site Settings</h2>
            <form method="POST" class="grid gap-4">
                Name: <input name="site_name" value="{{ conf.site_name }}" class="bg-gray-800 p-2 rounded">
                Logo URL: <input name="site_logo" value="{{ conf.site_logo }}" class="bg-gray-800 p-2 rounded">
                Notice: <textarea name="header_notice" class="bg-gray-800 p-2 rounded">{{ conf.header_notice }}</textarea>
                Slider Limit: <input name="slider_limit" value="{{ conf.slider_limit }}" class="bg-gray-800 p-2 rounded">
                <button class="bg-red-600 p-3 rounded font-bold">Update Settings</button>
            </form>
            <a href="/admin" class="block mt-4 text-blue-400">Back to Admin</a>
        </div>
    """, ui=UI_HEADER, conf=conf)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True, port=5000)
