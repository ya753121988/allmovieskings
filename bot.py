import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "premium_secret_key_fixed"

# --- আপনার ডাটাবেজ এবং API কি ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['DramaStoreDB']
movies_col = db['contents']
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
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    body { background: #080a10; color: #e2e8f0; font-family: 'Inter', sans-serif; }
    .glass { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .btn-red { background: linear-gradient(90deg, #e50914, #b20710); transition: 0.3s; }
    .btn-red:hover { opacity: 0.9; transform: scale(1.02); }
    .input-box { background: #151921; border: 1px solid #2d3748; padding: 12px; border-radius: 8px; width: 100%; outline: none; }
    .input-box:focus { border-color: #e50914; }
    .no-scrollbar::-webkit-scrollbar { display: none; }
</style>
"""

# --- ১. ইউজার হোমপেজ ---
@app.route('/')
def index():
    conf = settings_col.find_one({"id": "config"})
    search_q = request.args.get('s')
    if search_q:
        movies = list(movies_col.find({"title": {"$regex": search_q, "$options": "i"}}))
    else:
        movies = list(movies_col.find().sort("_id", -1))
    
    cats = list(cat_col.find())
    slider = list(movies_col.find().sort("views", -1).limit(int(conf.get('slider_limit', 10))))
    return render_template_string(HOME_HTML, ui=UI_HEAD, conf=conf, movies=movies, cats=cats, slider=slider)

# --- ২. ডিটেইল পেজ ---
@app.route('/view/<id>')
def view(id):
    movie = movies_col.find_one({"_id": ObjectId(id)})
    movies_col.update_one({"_id": ObjectId(id)}, {"$inc": {"views": 1}})
    conf = settings_col.find_one({"id": "config"})
    return render_template_string(DETAIL_HTML, ui=UI_HEAD, m=movie, conf=conf)

# --- ৩. অ্যাডমিন প্যানেল রুটস ---
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == settings_col.find_one({"id": "config"})['admin_user'] and \
           request.form.get('p') == settings_col.find_one({"id": "config"})['admin_pass']:
            session['admin'] = True
            return redirect('/admin')
    return render_template_string(LOGIN_HTML, ui=UI_HEAD)

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'): return redirect('/admin/login')
    return render_template_string(ADMIN_HTML, ui=UI_HEAD, cats=list(cat_col.find()))

@app.route('/admin/manage')
def admin_manage():
    if not session.get('admin'): return redirect('/admin/login')
    q = request.args.get('q', '')
    movies = list(movies_col.find({"title": {"$regex": q, "$options": "i"}}).sort("_id", -1))
    return render_template_string(MANAGE_HTML, ui=UI_HEAD, movies=movies)

# --- API: TMDB সার্চ এবং অটো-ফিল লজিক ---
@app.route('/api/tmdb_search')
def tmdb_search():
    query = request.args.get('q')
    mtype = request.args.get('t', 'movie')
    url = f"https://api.themoviedb.org/3/search/{mtype}?api_key={TMDB_API_KEY}&query={query}"
    return jsonify(requests.get(url).json())

@app.route('/api/tmdb_details')
def tmdb_details():
    tid = request.args.get('id')
    mtype = request.args.get('t', 'movie')
    url = f"https://api.themoviedb.org/3/{mtype}/{tid}?api_key={TMDB_API_KEY}&append_to_response=images"
    data = requests.get(url).json()
    # লোগো খুঁজে বের করা
    logos = data.get('images', {}).get('logos', [])
    logo_url = f"https://image.tmdb.org/t/p/original{logos[0]['file_path']}" if logos else ""
    return jsonify({"data": data, "logo": logo_url})

# --- অ্যাকশনস (Save, Delete, Category) ---
@app.route('/admin/save', methods=['POST'])
def save_content():
    if not session.get('admin'): return redirect('/')
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
        "links": []
    }
    movies_col.insert_one(content)
    return redirect('/admin')

@app.route('/admin/delete/<id>')
def delete_content(id):
    movies_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/manage')

@app.route('/admin/cat/add', methods=['POST'])
def add_cat():
    cat_col.insert_one({"name": request.form.get('cat_name')})
    return redirect('/admin')

@app.route('/admin/cat/del/<id>')
def del_cat(id):
    cat_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- HTML TEMPLATES (Inlined for single file bot.py) ---

HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <div class="flex items-center gap-4">
            <button onclick="document.getElementById('drawer').classList.toggle('hidden')" class="text-2xl"><i class="fa fa-bars"></i></button>
            <h1 class="text-2xl font-black text-red-600 tracking-tighter">{{ conf.site_name }}</h1>
        </div>
        <form class="hidden md:flex bg-gray-900/50 rounded-full border border-gray-700 px-4 py-1 items-center">
            <input name="s" placeholder="Search dramas..." class="bg-transparent outline-none p-1 w-64 text-sm">
            <button type="submit"><i class="fa fa-search text-gray-400"></i></button>
        </form>
    </nav>

    <div id="drawer" class="hidden fixed inset-0 z-[60]">
        <div class="absolute inset-0 bg-black/60" onclick="this.parentElement.classList.add('hidden')"></div>
        <div class="absolute left-0 top-0 h-full w-72 glass p-6 shadow-2xl">
            <h2 class="text-xl font-bold mb-8 text-red-500">Menu</h2>
            <div class="grid gap-4 font-semibold">
                <a href="/"><i class="fa fa-home mr-2"></i> Home</a>
                <div class="text-gray-500 text-xs uppercase mt-4">Categories</div>
                {% for c in cats %}<a href="/?s={{ c.name }}"><i class="fa fa-folder-open mr-2 text-red-400"></i> {{ c.name }}</a>{% endfor %}
                <hr class="border-gray-800 my-4">
                <a href="/admin/login" class="text-sm text-gray-400">Admin Panel</a>
            </div>
        </div>
    </div>

    <div class="bg-red-600/20 text-red-500 text-center py-2 text-xs font-bold border-y border-red-900/30 marquee">{{ conf.header_notice }}</div>

    <main class="p-4 md:px-16">
        <h2 class="text-xl font-bold mb-4 mt-6 flex items-center gap-2"><i class="fa fa-fire text-orange-500"></i> Trending Now</h2>
        <div class="flex gap-4 overflow-x-auto no-scrollbar pb-6">
            {% for m in slider %}
            <div class="min-w-[300px] h-44 relative rounded-2xl overflow-hidden shadow-2xl cursor-pointer group" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover group-hover:scale-110 transition duration-700">
                <div class="absolute inset-0 bg-gradient-to-t from-black via-transparent p-4 flex flex-col justify-end">
                    <p class="font-bold text-lg leading-tight">{{ m.title }}</p>
                    <span class="text-[10px] text-gray-300 uppercase tracking-tighter">{{ m.lang }} • {{ m.year }}</span>
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="flex justify-between items-end mb-6 mt-10">
            <h2 class="text-2xl font-black italic">Latest Uploads</h2>
            <div class="text-gray-500 text-sm">Showing {{ movies|length }} Items</div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
            {% for m in movies %}
            <div class="cursor-pointer group" onclick="location.href='/view/{{ m._id }}'">
                <div class="relative overflow-hidden rounded-xl aspect-[2/3] shadow-lg border border-gray-800">
                    <img src="{{ m.poster }}" class="w-full h-full object-cover group-hover:scale-105 transition duration-500">
                    <div class="absolute top-2 right-2 glass px-2 py-1 rounded text-[10px] font-bold">{{ m.lang }}</div>
                </div>
                <div class="mt-3">
                    <h3 class="font-bold text-sm truncate group-hover:text-red-500 transition">{{ m.title }}</h3>
                    <p class="text-[10px] text-gray-500 uppercase">{{ m.year }} • {{ m.type }}</p>
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
        <img src="{{ m.backdrop }}" class="w-full h-full object-cover opacity-40">
        <div class="absolute inset-0 bg-gradient-to-t from-[#080a10] via-[#080a10]/50 to-transparent"></div>
        <div class="absolute top-8 left-8">
            <button onclick="history.back()" class="glass h-12 w-12 rounded-full flex items-center justify-center hover:bg-red-600 transition"><i class="fa fa-arrow-left"></i></button>
        </div>
        <div class="absolute bottom-12 left-6 md:left-20 max-w-4xl">
            {% if m.logo %}<img src="{{ m.logo }}" class="w-64 md:w-96 mb-6">
            {% else %}<h1 class="text-4xl md:text-7xl font-black mb-4">{{ m.title }}</h1>{% endif %}
            <div class="flex gap-4 text-sm font-bold text-gray-300 mb-6 items-center">
                <span class="bg-red-600 text-white px-2 py-0.5 rounded text-xs">HD</span>
                <span>{{ m.year }}</span>
                <span>{{ m.lang }}</span>
                <span>{{ m.views }} Views</span>
            </div>
            <p class="text-gray-300 text-sm md:text-lg leading-relaxed line-clamp-3 md:line-clamp-none">{{ m.story }}</p>
        </div>
    </div>

    <div class="p-6 md:p-20">
        <h3 class="text-2xl font-bold mb-8 border-l-4 border-red-600 pl-4">Download & Stream</h3>
        <div class="grid gap-4 max-w-5xl">
            {% for link in m.links %}
            <div class="glass p-5 rounded-2xl flex flex-wrap justify-between items-center gap-4 hover:border-red-500/50 transition">
                <div class="flex items-center gap-4">
                    <div class="h-12 w-12 rounded-full bg-red-600/20 flex items-center justify-center text-red-500"><i class="fa fa-play text-xl"></i></div>
                    <div>
                        <div class="font-bold text-lg">{{ link.quality }}</div>
                        <div class="text-xs text-gray-500 uppercase tracking-widest">Premium Server</div>
                    </div>
                </div>
                <div class="flex gap-3 w-full md:w-auto">
                    <a href="{{ link.tg }}" class="flex-1 md:flex-none text-center bg-sky-600 hover:bg-sky-700 px-6 py-3 rounded-xl font-bold text-sm"><i class="fab fa-telegram mr-2"></i> Telegram</a>
                    <a href="{{ link.direct }}" class="flex-1 md:flex-none text-center bg-white text-black hover:bg-gray-200 px-6 py-3 rounded-xl font-bold text-sm"><i class="fa fa-download mr-2"></i> Direct Link</a>
                </div>
            </div>
            {% endfor %}
            {% if not m.links %}<p class="text-gray-500">No links added yet.</p>{% endif %}
        </div>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Panel</title></head>
<body class="flex flex-col md:flex-row min-h-screen">
    <!-- Sidebar -->
    <div class="w-full md:w-72 glass p-8 sticky top-0 h-auto md:h-screen">
        <h2 class="text-red-500 font-black text-3xl mb-12 italic tracking-tighter">ADMIN BOX</h2>
        <div class="grid gap-6">
            <a href="/admin" class="flex items-center gap-3 text-red-500 font-bold"><i class="fa fa-plus-circle"></i> Add Content</a>
            <a href="/admin/manage" class="flex items-center gap-3 hover:text-red-400"><i class="fa fa-tasks"></i> Manage Content</a>
            <hr class="border-gray-800">
            <div class="text-xs text-gray-600 font-bold uppercase">Categories</div>
            <form action="/admin/cat/add" method="POST" class="flex gap-2">
                <input name="cat_name" placeholder="New Category" class="bg-black/40 border border-gray-800 p-2 rounded-lg text-xs outline-none focus:border-red-500 flex-1">
                <button class="bg-red-600 p-2 rounded-lg"><i class="fa fa-plus"></i></button>
            </form>
            <div class="grid gap-2 max-h-40 overflow-y-auto no-scrollbar">
                {% for c in cats %}
                <div class="flex justify-between items-center text-xs bg-white/5 p-2 rounded">
                    {{ c.name }} <a href="/admin/cat/del/{{ c._id }}" class="text-red-500"><i class="fa fa-trash"></i></a>
                </div>
                {% endfor %}
            </div>
            <a href="/logout" class="text-gray-500 mt-20 hover:text-white"><i class="fa fa-sign-out"></i> Logout</a>
        </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 p-6 md:p-12 overflow-y-auto">
        <h2 class="text-3xl font-black mb-8">Add New Drama / Movie</h2>
        
        <div class="mb-10 p-8 glass rounded-3xl">
            <h3 class="text-xl font-bold mb-6 text-red-500 flex items-center gap-2"><i class="fa fa-magic"></i> Step 1: Auto-Fetch from TMDB</h3>
            <div class="flex flex-wrap gap-4 mb-4">
                <select id="mtype" class="bg-gray-800 p-3 rounded-xl border border-gray-700 outline-none">
                    <option value="movie">Movie</option>
                    <option value="tv">TV Series</option>
                </select>
                <input id="tmdb_query" placeholder="Search by Name (e.g. Squid Game)" class="input-box flex-1">
                <button onclick="searchTMDB()" class="btn-red px-8 py-3 rounded-xl font-bold">Search</button>
            </div>
            <div id="results" class="flex gap-4 overflow-x-auto no-scrollbar py-4"></div>
        </div>

        <form action="/admin/save" method="POST" class="glass p-8 rounded-3xl">
            <h3 class="text-xl font-bold mb-8 text-blue-400 flex items-center gap-2"><i class="fa fa-edit"></i> Step 2: Confirm Details</h3>
            <div class="grid md:grid-cols-2 gap-6">
                <div>
                    <label class="text-xs text-gray-500 font-bold ml-1">Title</label>
                    <input name="title" id="f_title" class="input-box mb-4" required>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="text-xs text-gray-500 font-bold ml-1">Year</label>
                            <input name="year" id="f_year" class="input-box">
                        </div>
                        <div>
                            <label class="text-xs text-gray-500 font-bold ml-1">Language</label>
                            <input name="lang" id="f_lang" class="input-box">
                        </div>
                    </div>
                    <label class="text-xs text-gray-500 font-bold ml-1 mt-4 block">Poster (Vertical)</label>
                    <input name="poster" id="f_poster" class="input-box mb-4">
                    <label class="text-xs text-gray-500 font-bold ml-1 block">Backdrop (Landscape)</label>
                    <input name="backdrop" id="f_backdrop" class="input-box mb-4">
                    <label class="text-xs text-gray-500 font-bold ml-1 block">Logo PNG URL</label>
                    <input name="logo" id="f_logo" class="input-box mb-4">
                </div>
                <div>
                    <label class="text-xs text-gray-500 font-bold ml-1">Category (Select Multiple)</label>
                    <div class="grid grid-cols-2 gap-2 bg-black/30 p-4 rounded-xl border border-gray-800 h-[120px] overflow-y-auto mb-4">
                        {% for c in cats %}
                        <label class="text-xs flex items-center gap-2"><input type="checkbox" name="cats" value="{{ c.name }}"> {{ c.name }}</label>
                        {% endfor %}
                    </div>
                    <label class="text-xs text-gray-500 font-bold ml-1">Storyline</label>
                    <textarea name="story" id="f_story" class="input-box h-[150px]"></textarea>
                    <input type="hidden" name="type" id="f_type" value="movie">
                    <button class="w-full btn-red py-4 rounded-2xl font-black text-xl mt-6">SAVE TO DATABASE</button>
                </div>
            </div>
        </form>
    </div>

    <script>
        async function searchTMDB() {
            const q = document.getElementById('tmdb_query').value;
            const t = document.getElementById('mtype').value;
            const res = await fetch(`/api/tmdb_search?q=${q}&t=${t}`);
            const data = await res.json();
            const div = document.getElementById('results');
            div.innerHTML = '';
            data.results.forEach(m => {
                div.innerHTML += `
                    <div class="min-w-[120px] cursor-pointer text-center group" onclick="fillForm('${m.id}', '${t}')">
                        <img src="https://image.tmdb.org/t/p/w200${m.poster_path}" class="rounded-lg mb-2 border border-gray-800 group-hover:border-red-500">
                        <p class="text-[10px] truncate w-full">${m.title || m.name}</p>
                    </div>`;
            });
        }

        async function fillForm(id, type) {
            const res = await fetch(`/api/tmdb_details?id=${id}&t=${type}`);
            const json = await res.json();
            const d = json.data;
            document.getElementById('f_title').value = d.title || d.name;
            document.getElementById('f_year').value = (d.release_date || d.first_air_date).split('-')[0];
            document.getElementById('f_lang').value = d.original_language.toUpperCase();
            document.getElementById('f_poster').value = 'https://image.tmdb.org/t/p/w500' + d.poster_path;
            document.getElementById('f_backdrop').value = 'https://image.tmdb.org/t/p/original' + d.backdrop_path;
            document.getElementById('f_logo').value = json.logo;
            document.getElementById('f_story').value = d.overview;
            document.getElementById('f_type').value = type;
            alert("Data fetched! Please verify and Save.");
        }
    </script>
</body>
</html>
"""

MANAGE_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Manage Content</title></head>
<body class="flex">
    <div class="w-72 glass p-8 h-screen sticky top-0">
        <a href="/admin" class="text-xl font-bold text-gray-500 block mb-10 hover:text-white"><i class="fa fa-arrow-left"></i> Dashboard</a>
    </div>
    <div class="flex-1 p-12">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-3xl font-black">Manage Contents</h2>
            <form class="bg-gray-800 px-4 py-2 rounded-xl border border-gray-700">
                <input name="q" placeholder="Search to Edit/Delete..." class="bg-transparent outline-none">
                <button><i class="fa fa-search text-gray-400"></i></button>
            </form>
        </div>
        <div class="grid gap-4">
            {% for m in movies %}
            <div class="glass p-4 rounded-2xl flex items-center justify-between">
                <div class="flex items-center gap-4">
                    <img src="{{ m.poster }}" class="h-16 w-12 rounded object-cover border border-gray-700">
                    <div>
                        <div class="font-bold text-lg leading-tight">{{ m.title }}</div>
                        <div class="text-xs text-gray-500 uppercase">{{ m.year }} • {{ m.lang }} • {{ m.views }} Views</div>
                    </div>
                </div>
                <div class="flex gap-2">
                    <button class="bg-blue-600/20 text-blue-400 p-3 rounded-xl hover:bg-blue-600 hover:text-white transition" onclick="alert('Open Edit Form Logic Here')"><i class="fa fa-edit"></i></button>
                    <a href="/admin/delete/{{ m._id }}" class="bg-red-600/20 text-red-500 p-3 rounded-xl hover:bg-red-600 hover:text-white transition" onclick="return confirm('Sure to delete?')"><i class="fa fa-trash"></i></a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Login</title></head>
<body class="flex items-center justify-center min-h-screen">
    <form method="POST" class="glass p-12 rounded-[40px] w-full max-w-md shadow-2xl border border-white/10">
        <h2 class="text-4xl font-black mb-8 text-center text-red-600 tracking-tighter">ADMIN LOGIN</h2>
        <div class="grid gap-6">
            <input name="u" placeholder="Username" class="input-box text-center text-lg" required>
            <input name="p" type="password" placeholder="Password" class="input-box text-center text-lg" required>
            <button class="btn-red py-4 rounded-2xl font-black text-xl mt-4 shadow-xl shadow-red-900/20">ACCESS DASHBOARD</button>
        </div>
        <p class="text-center text-gray-600 mt-8 text-xs font-bold uppercase tracking-widest">Premium Drama Store System</p>
    </form>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
