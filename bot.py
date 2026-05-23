import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "premium_drama_store_secret_99"

# --- ডাটাবেজ এবং API কি (আপনার দেওয়া তথ্য) ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['DramaStoreDB']
contents_col = db['contents']
settings_col = db['site_config']
cat_col = db['categories']

# ডিফল্ট সেটিংস
if not settings_col.find_one({"id": "config"}):
    settings_col.insert_one({
        "id": "config", "site_name": "DRAMA-FLIX", "site_logo": "",
        "header_notice": "Welcome to Premium Drama Store",
        "admin_user": "admin", "admin_pass": "1234", "slider_limit": 10
    })

# --- UI STYLES (Tailwind Premium) ---
UI_HEAD = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
<style>
    body { background: #06080f; color: #e2e8f0; font-family: 'Inter', sans-serif; overflow-x: hidden; }
    .glass { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .btn-red { background: linear-gradient(90deg, #e50914, #b20710); transition: 0.3s; }
    .input-box { background: #11141b; border: 1px solid #1f2937; padding: 12px; border-radius: 12px; width: 100%; outline: none; color: white; }
    .input-box:focus { border-color: #e50914; }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .season-tab.active { border-bottom: 3px solid #e50914; color: #e50914; }
    .marquee { white-space: nowrap; animation: marquee 20s linear infinite; }
    @keyframes marquee { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
</style>
"""

# --- ১. ইউজার হোমপেজ ---
@app.route('/')
def index():
    conf = settings_col.find_one({"id": "config"})
    search_q = request.args.get('s')
    query = {"title": {"$regex": search_q, "$options": "i"}} if search_q else {}
    movies = list(contents_col.find(query).sort("_id", -1))
    cats = list(cat_col.find())
    slider = list(contents_col.find().sort("views", -1).limit(int(conf.get('slider_limit', 10))))
    return render_template_string(HOME_HTML, ui=UI_HEAD, conf=conf, movies=movies, cats=cats, slider=slider)

# --- ২. ডিটেইল পেজ (মুভি ও সিরিজ আলাদা লজিক) ---
@app.route('/view/<id>')
def view(id):
    item = contents_col.find_one({"_id": ObjectId(id)})
    contents_col.update_one({"_id": ObjectId(id)}, {"$inc": {"views": 1}})
    conf = settings_col.find_one({"id": "config"})
    return render_template_string(DETAIL_HTML, ui=UI_HEAD, m=item, conf=conf)

# --- ৩. অ্যাডমিন প্যানেল ---
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    conf = settings_col.find_one({"id": "config"})
    if request.method == 'POST':
        if request.form.get('u') == conf['admin_user'] and request.form.get('p') == conf['admin_pass']:
            session['admin'] = True
            return redirect('/admin')
    return render_template_string(LOGIN_HTML, ui=UI_HEAD)

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'): return redirect('/admin/login')
    return render_template_string(ADMIN_HTML, ui=UI_HEAD, cats=list(cat_col.find()))

# --- ৪. সেভ ও আপডেট লজিক ---
@app.route('/admin/save', methods=['POST'])
def save_content():
    content = {
        "title": request.form.get('title'),
        "lang": request.form.get('lang'),
        "year": request.form.get('year'),
        "story": request.form.get('story'),
        "poster": request.form.get('poster'),
        "backdrop": request.form.get('backdrop'),
        "logo": request.form.get('logo'),
        "category": request.form.getlist('cats'),
        "type": request.form.get('type'),
        "views": 0,
        "movie_links": [], # শুধু মুভির জন্য
        "seasons": []      # শুধু সিরিজের জন্য
    }
    contents_col.insert_one(content)
    return redirect('/admin/manage')

# মুভির ডাউনলোড লিংক অ্যাড
@app.route('/admin/add_movie_link', methods=['POST'])
def add_movie_link():
    m_id = request.form.get('m_id')
    link = {"quality": request.form.get('q'), "tg": request.form.get('tg'), "direct": request.form.get('direct')}
    contents_col.update_one({"_id": ObjectId(m_id)}, {"$push": {"movie_links": link}})
    return redirect('/admin/manage')

# সিরিজের ইপিসোড অ্যাড
@app.route('/admin/add_episode', methods=['POST'])
def add_episode():
    s_id = request.form.get('s_id')
    season_num = request.form.get('season_num')
    ep_num = request.form.get('ep_num')
    
    # কোয়ালিটি লিংক লিস্ট তৈরি
    qualities = request.form.get('qualities').split(',') # 480p|link1|link2, 720p|link1|link2
    links = []
    for q in qualities:
        parts = q.split('|')
        if len(parts) == 3:
            links.append({"quality": parts[0], "tg": parts[1], "direct": parts[2]})

    episode = {"ep_num": ep_num, "links": links}
    
    # ডাটাবেজে সিজন চেক ও পুশ
    contents_col.update_one(
        {"_id": ObjectId(s_id), "seasons.season_num": season_num},
        {"$push": {"seasons.$.episodes": episode}}
    ) or contents_col.update_one(
        {"_id": ObjectId(s_id)},
        {"$push": {"seasons": {"season_num": season_num, "episodes": [episode]}}}
    )
    return redirect('/admin/manage')

# --- ৫. এপিআই (TMDB) ---
@app.route('/api/tmdb_search')
def tmdb_search():
    query = request.args.get('q')
    mtype = request.args.get('t', 'movie')
    url = f"https://api.themoviedb.org/3/search/{mtype}?api_key={TMDB_API_KEY}&query={query}"
    return jsonify(requests.get(url).json())

@app.route('/api/tmdb_details')
def tmdb_details():
    tid = request.args.get('id'); mtype = request.args.get('t')
    data = requests.get(f"https://api.themoviedb.org/3/{mtype}/{tid}?api_key={TMDB_API_KEY}&append_to_response=images").json()
    logos = data.get('images', {}).get('logos', [])
    logo_url = f"https://image.tmdb.org/t/p/original{logos[0]['file_path']}" if logos else ""
    return jsonify({"data": data, "logo": logo_url})

# --- ৬. ডিলিট ও ম্যানেজ ---
@app.route('/admin/manage')
def admin_manage():
    if not session.get('admin'): return redirect('/admin/login')
    items = list(contents_col.find().sort("_id", -1))
    return render_template_string(MANAGE_HTML, ui=UI_HEAD, items=items)

@app.route('/admin/delete/<id>')
def delete_item(id):
    contents_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/manage')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# -----------------------------------------------------------
# HTML TEMPLATES (Inlined)
# -----------------------------------------------------------

HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <div class="flex items-center gap-4">
            <button onclick="document.getElementById('drawer').classList.toggle('hidden')" class="text-2xl"><i class="fa fa-bars text-red-500"></i></button>
            <h1 class="text-2xl font-black text-red-600 tracking-tighter">{{ conf.site_name }}</h1>
        </div>
        <form class="hidden md:flex bg-gray-900/50 rounded-full border border-gray-700 px-4 py-1 items-center">
            <input name="s" placeholder="Search dramas & movies..." class="bg-transparent outline-none p-1 w-64 text-sm">
            <button type="submit"><i class="fa fa-search text-gray-400"></i></button>
        </form>
    </nav>

    <div id="drawer" class="hidden fixed inset-0 z-[60]">
        <div class="absolute inset-0 bg-black/80" onclick="this.parentElement.classList.add('hidden')"></div>
        <div class="absolute left-0 top-0 h-full w-72 glass p-8">
            <h2 class="text-2xl font-black mb-8 text-red-600 italic">Menu</h2>
            <div class="grid gap-6 font-semibold">
                <a href="/" class="hover:text-red-500"><i class="fa fa-home mr-3"></i> Home</a>
                <div class="text-gray-500 text-[10px] uppercase tracking-widest mt-4">Categories</div>
                {% for c in cats %}<a href="/?s={{ c.name }}" class="hover:text-red-500 text-sm"><i class="fa fa-tag mr-3 text-red-900"></i> {{ c.name }}</a>{% endfor %}
                <hr class="border-gray-800 my-4">
                <a href="/admin/login" class="text-sm text-gray-500"><i class="fa fa-lock mr-3"></i> Admin Login</a>
            </div>
        </div>
    </div>

    <div class="bg-red-600/10 text-red-500 py-2 border-y border-red-900/30 overflow-hidden relative h-8">
        <div class="marquee absolute font-bold text-xs">{{ conf.header_notice }}</div>
    </div>

    <main class="p-4 md:px-16">
        <!-- Slider -->
        <h2 class="text-xl font-bold mb-4 mt-6 text-red-500 italic"><i class="fa fa-bolt"></i> TRENDING NOW</h2>
        <div class="flex gap-4 overflow-x-auto no-scrollbar pb-6">
            {% for m in slider %}
            <div class="min-w-[300px] h-44 relative rounded-2xl overflow-hidden shadow-2xl cursor-pointer group flex-shrink-0" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover group-hover:scale-110 transition duration-700">
                <div class="absolute inset-0 bg-gradient-to-t from-black via-black/20 p-4 flex flex-col justify-end">
                    <p class="font-bold text-lg">{{ m.title }}</p>
                    <span class="text-[10px] text-gray-400 uppercase font-black tracking-widest">{{ m.lang }} • {{ m.year }}</span>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Content Grid -->
        <div class="flex justify-between items-end mb-8 mt-10">
            <h2 class="text-2xl font-black italic border-l-4 border-red-600 pl-4">LATEST UPLOADS</h2>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
            {% for m in movies %}
            <div class="cursor-pointer group" onclick="location.href='/view/{{ m._id }}'">
                <div class="relative overflow-hidden rounded-2xl aspect-[2/3] shadow-lg border border-gray-800">
                    <img src="{{ m.poster }}" class="w-full h-full object-cover group-hover:scale-105 transition duration-500">
                    <div class="absolute top-2 right-2 glass px-2 py-1 rounded text-[10px] font-bold text-red-500">{{ m.lang }}</div>
                    {% if m.type == 'tv' %}<div class="absolute bottom-2 left-2 bg-red-600 px-2 py-1 rounded text-[8px] font-black italic">SERIES</div>{% endif %}
                </div>
                <div class="mt-3 px-1">
                    <h3 class="font-bold text-sm truncate group-hover:text-red-500 transition">{{ m.title }}</h3>
                    <p class="text-[10px] text-gray-500 uppercase font-bold">{{ m.year }} • {{ m.lang }}</p>
                </div>
            </div>
            {% endfor %}
        </div>
    </main>
</body>
</html>
"""

DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ m.title }}</title></head>
<body>
    <div class="relative h-[60vh] md:h-[80vh]">
        <img src="{{ m.backdrop }}" class="w-full h-full object-cover opacity-30">
        <div class="absolute inset-0 bg-gradient-to-t from-[#06080f] via-transparent"></div>
        <div class="absolute top-8 left-8">
            <button onclick="history.back()" class="glass h-12 w-12 rounded-full flex items-center justify-center hover:bg-red-600 transition shadow-xl"><i class="fa fa-arrow-left text-xl"></i></button>
        </div>
        <div class="absolute bottom-12 left-6 md:left-20 max-w-4xl">
            {% if m.logo %}<img src="{{ m.logo }}" class="w-64 md:w-96 mb-6">
            {% else %}<h1 class="text-4xl md:text-7xl font-black mb-4 italic tracking-tighter">{{ m.title }}</h1>{% endif %}
            <div class="flex gap-4 text-xs font-black text-gray-400 mb-6 items-center tracking-widest">
                <span class="bg-red-600 text-white px-2 py-1 rounded">HD</span>
                <span>{{ m.year }}</span>
                <span>{{ m.lang }}</span>
                <span><i class="fa fa-eye"></i> {{ m.views }}</span>
            </div>
            <p class="text-gray-300 text-sm md:text-lg leading-relaxed line-clamp-3">{{ m.story }}</p>
        </div>
    </div>

    <div class="p-6 md:p-20">
        {% if m.type == 'movie' %}
            <h3 class="text-2xl font-black mb-8 border-l-4 border-red-600 pl-4 italic">DOWNLOAD LINKS</h3>
            <div class="grid gap-4 max-w-4xl">
                {% for link in m.movie_links %}
                <div class="glass p-5 rounded-2xl flex justify-between items-center hover:border-red-600/50 transition">
                    <div class="font-bold text-red-500 uppercase tracking-widest"><i class="fa fa-film mr-2"></i> {{ link.quality }}</div>
                    <div class="flex gap-3">
                        <a href="{{ link.tg }}" class="bg-sky-600 px-6 py-2 rounded-xl font-bold text-xs"><i class="fab fa-telegram"></i></a>
                        <a href="{{ link.direct }}" class="bg-white text-black px-6 py-2 rounded-xl font-bold text-xs italic">DIRECT DOWNLOAD</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <!-- সিরিজ সিজন ও ইপিসোড UI -->
            <div class="mb-10">
                <h3 class="text-2xl font-black mb-8 border-l-4 border-red-600 pl-4 italic">SELECT SEASON</h3>
                <div class="flex gap-4 overflow-x-auto no-scrollbar border-b border-gray-800 pb-2">
                    {% for s in m.seasons %}
                    <button onclick="showSeason('{{ s.season_num }}')" class="season-tab px-6 py-2 font-black italic uppercase tracking-tighter" id="tab-{{ s.season_num }}">Season {{ s.season_num }}</button>
                    {% endfor %}
                </div>
            </div>

            {% for s in m.seasons %}
            <div class="season-content hidden grid gap-4" id="season-{{ s.season_num }}">
                <h4 class="text-gray-500 text-xs font-bold mb-4 uppercase">Episodes List</h4>
                {% for ep in s.episodes %}
                <div class="glass p-6 rounded-3xl">
                    <div class="font-bold mb-4 text-gray-400">Episode {{ ep.ep_num }}</div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {% for link in ep.links %}
                        <div class="bg-white/5 p-3 rounded-2xl flex justify-between items-center border border-white/5">
                            <span class="text-xs font-black text-red-600 tracking-widest">{{ link.quality }}</span>
                            <div class="flex gap-2">
                                <a href="{{ link.tg }}" class="text-sky-500 p-2"><i class="fab fa-telegram text-xl"></i></a>
                                <a href="{{ link.direct }}" class="bg-white text-black text-[10px] px-4 py-1.5 rounded-full font-black uppercase">Download</a>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        {% endif %}
    </div>

    <script>
        function showSeason(num) {
            document.querySelectorAll('.season-content').forEach(c => c.classList.add('hidden'));
            document.querySelectorAll('.season-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('season-' + num).classList.remove('hidden');
            document.getElementById('tab-' + num).classList.add('active');
        }
        // অটো প্রথম সিজন দেখানো
        window.onload = () => {
            let first = document.querySelector('.season-tab');
            if(first) first.click();
        }
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Panel</title></head>
<body class="flex flex-col md:flex-row min-h-screen">
    <div class="w-full md:w-80 glass p-8 h-screen sticky top-0 overflow-y-auto">
        <h2 class="text-red-600 font-black text-4xl mb-12 italic tracking-tighter">ADMIN</h2>
        <div class="grid gap-6 font-bold">
            <a href="/admin" class="text-red-500"><i class="fa fa-plus-circle mr-2"></i> Add Content</a>
            <a href="/admin/manage" class="text-gray-500 hover:text-white"><i class="fa fa-tasks mr-2"></i> Manage/Links</a>
            <hr class="border-gray-800">
            <h3 class="text-[10px] text-gray-600 uppercase tracking-widest">Category Manager</h3>
            <form action="/admin/cat/add" method="POST" class="flex gap-2">
                <input name="cat_name" placeholder="Name" class="input-box p-2 text-xs flex-1">
                <button class="bg-red-600 p-2 px-4 rounded-xl"><i class="fa fa-plus"></i></button>
            </form>
            <a href="/logout" class="text-red-900 mt-20 text-xs">Logout Session</a>
        </div>
    </div>

    <div class="flex-1 p-6 md:p-12 overflow-y-auto">
        <h2 class="text-3xl font-black mb-10 italic">UPLOAD CONTENT</h2>
        
        <div class="glass p-8 rounded-[40px] mb-10 border-red-600/20">
            <h3 class="text-xl font-black mb-6 text-red-600"><i class="fa fa-search"></i> 1. TMDB Auto Search</h3>
            <div class="flex gap-4">
                <select id="mtype" class="input-box w-32">
                    <option value="movie">Movie</option>
                    <option value="tv">TV Series</option>
                </select>
                <input id="tmdb_q" placeholder="Enter Drama/Movie Name..." class="input-box flex-1">
                <button onclick="searchTMDB()" class="btn-red px-10 rounded-2xl font-black italic">SEARCH</button>
            </div>
            <div id="results" class="flex gap-4 overflow-x-auto no-scrollbar py-6"></div>
        </div>

        <form action="/admin/save" method="POST" class="glass p-10 rounded-[40px] grid md:grid-cols-2 gap-8">
            <div>
                <label class="text-[10px] text-gray-500 font-black uppercase">Title</label>
                <input name="title" id="f_title" class="input-box mb-4" required>
                <div class="grid grid-cols-2 gap-4">
                    <input name="year" id="f_year" placeholder="Year" class="input-box">
                    <input name="lang" id="f_lang" placeholder="Lang" class="input-box">
                </div>
                <label class="text-[10px] text-gray-500 font-black uppercase mt-4 block">Poster & Backdrop</label>
                <input name="poster" id="f_poster" placeholder="Poster URL" class="input-box mb-2">
                <input name="backdrop" id="f_backdrop" placeholder="Backdrop URL" class="input-box mb-2">
                <input name="logo" id="f_logo" placeholder="Logo PNG URL" class="input-box">
            </div>
            <div>
                <label class="text-[10px] text-gray-500 font-black uppercase">Categories</label>
                <div class="grid grid-cols-2 gap-2 bg-black/40 p-4 rounded-2xl border border-gray-800 h-28 overflow-y-auto mb-4">
                    {% for c in cats %}<label class="text-xs"><input type="checkbox" name="cats" value="{{ c.name }}"> {{ c.name }}</label>{% endfor %}
                </div>
                <label class="text-[10px] text-gray-500 font-black uppercase">Storyline</label>
                <textarea name="story" id="f_story" class="input-box h-32"></textarea>
                <input type="hidden" name="type" id="f_type">
                <button class="w-full btn-red py-4 rounded-3xl font-black text-xl mt-6 italic">SAVE CONTENT</button>
            </div>
        </form>
    </div>

    <script>
        async function searchTMDB() {
            const q = document.getElementById('tmdb_q').value;
            const t = document.getElementById('mtype').value;
            const res = await fetch(`/api/tmdb_search?q=${q}&t=${t}`);
            const data = await res.json();
            const div = document.getElementById('results');
            div.innerHTML = '';
            data.results.forEach(m => {
                div.innerHTML += `<div class="min-w-[120px] cursor-pointer" onclick="fill('${m.id}', '${t}')"><img src="https://image.tmdb.org/t/p/w200${m.poster_path}" class="rounded-xl border-2 border-transparent hover:border-red-600"></div>`;
            });
        }
        async function fill(id, type) {
            const res = await fetch(`/api/tmdb_details?id=${id}&t=${type}`);
            const j = await res.json(); const d = j.data;
            document.getElementById('f_title').value = d.title || d.name;
            document.getElementById('f_year').value = (d.release_date || d.first_air_date).split('-')[0];
            document.getElementById('f_lang').value = d.original_language.toUpperCase();
            document.getElementById('f_poster').value = 'https://image.tmdb.org/t/p/w500' + d.poster_path;
            document.getElementById('f_backdrop').value = 'https://image.tmdb.org/t/p/original' + d.backdrop_path;
            document.getElementById('f_logo').value = j.logo;
            document.getElementById('f_story').value = d.overview;
            document.getElementById('f_type').value = type;
            alert("Data Loaded!");
        }
    </script>
</body>
</html>
"""

MANAGE_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Manage Links</title></head>
<body class="p-10">
    <a href="/admin" class="text-red-500 font-black mb-10 block italic uppercase tracking-tighter"><i class="fa fa-arrow-left"></i> Dashboard</a>
    <h2 class="text-3xl font-black mb-10 italic">MANAGE LINKS & EPISODES</h2>

    <div class="grid gap-8">
        {% for m in items %}
        <div class="glass p-8 rounded-[40px] border-white/5 shadow-2xl">
            <div class="flex justify-between items-center mb-6">
                <div class="flex items-center gap-6">
                    <img src="{{ m.poster }}" class="h-20 w-16 rounded-xl object-cover">
                    <div>
                        <h4 class="text-xl font-black italic">{{ m.title }}</h4>
                        <span class="text-xs font-bold text-gray-500 uppercase">{{ m.type }} | {{ m.year }}</span>
                    </div>
                </div>
                <a href="/admin/delete/{{ m._id }}" class="text-red-900 text-xs uppercase font-black" onclick="return confirm('Delete?')">Delete Content</a>
            </div>

            {% if m.type == 'movie' %}
                <!-- মুভি লিংক ফরম -->
                <form action="/admin/add_movie_link" method="POST" class="grid md:grid-cols-4 gap-4 bg-black/40 p-6 rounded-3xl border border-gray-800">
                    <input type="hidden" name="m_id" value="{{ m._id }}">
                    <input name="q" placeholder="Quality (e.g. 1080p HD)" class="input-box p-2 text-xs">
                    <input name="tg" placeholder="Telegram Link" class="input-box p-2 text-xs">
                    <input name="direct" placeholder="Direct Download Link" class="input-box p-2 text-xs">
                    <button class="bg-blue-600 rounded-xl font-black text-[10px] uppercase">Add Quality Link</button>
                </form>
                <div class="mt-4 flex gap-2 flex-wrap">
                    {% for l in m.movie_links %}<span class="bg-gray-800 px-3 py-1 rounded-full text-[10px]">{{ l.quality }}</span>{% endfor %}
                </div>
            {% else %}
                <!-- সিরিজ ইপিসোড ফরম -->
                <form action="/admin/add_episode" method="POST" class="grid md:grid-cols-5 gap-4 bg-black/40 p-6 rounded-3xl border border-gray-800">
                    <input type="hidden" name="s_id" value="{{ m._id }}">
                    <input name="season_num" placeholder="Season No." class="input-box p-2 text-xs">
                    <input name="ep_num" placeholder="Episode No." class="input-box p-2 text-xs">
                    <input name="qualities" placeholder="Format: Quality|TG_Link|Direct_Link, Next_Quality|TG|Direct" class="input-box p-2 text-xs col-span-2">
                    <button class="bg-indigo-600 rounded-xl font-black text-[10px] uppercase">Add Episode</button>
                </form>
                <div class="mt-4 text-[10px] text-gray-500 font-bold uppercase">
                    Seasons Added: {% for s in m.seasons %} Season {{ s.season_num }} ({{ s.episodes|length }} Ep) | {% endfor %}
                </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
