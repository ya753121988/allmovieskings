import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "ULTIMATE_DRAMA_KEY_2024"

# --- ডাটাবেজ এবং API কি ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['DramaStoreDB']
contents_col = db['contents']
settings_col = db['mega_config']
cat_col = db['categories']

# ডিফল্ট মাস্টার সেটিংস
if not settings_col.find_one({"id": "config"}):
    settings_col.insert_one({
        "id": "config",
        "site_name": "DRAMA-FLIX",
        "site_logo": "https://i.ibb.co/logo.png",
        "header_notice": "Welcome to the Most Premium Drama Store Online!",
        "admin_user": "admin",
        "admin_pass": "1234",
        "movie_limit": 10,
        "series_limit": 10,
        "slider_limit": 5,
        "primary_color": "#e50914",
        "footer_text": "© 2024 All Rights Reserved"
    })

# --- UI STYLES (Ultra Premium) ---
UI_HEAD = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    :root { --p: #e50914; }
    body { background: #05070a; color: #f8fafc; font-family: 'Inter', sans-serif; }
    .glass { background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    .admin-card { background: #0f172a; border: 1px solid #1e293b; padding: 20px; border-radius: 15px; }
    .btn-red { background: var(--p); color: white; padding: 10px 20px; border-radius: 8px; font-weight: bold; transition: 0.3s; }
    .btn-red:hover { background: #b20710; }
    .input-field { background: #1e293b; border: 1px solid #334155; color: white; padding: 12px; border-radius: 10px; width: 100%; outline: none; }
    .input-field:focus { border-color: var(--p); }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .tab-active { border-bottom: 3px solid var(--p); color: var(--p); font-weight: 800; }
</style>
"""

# --- ১. ইউজার হোমপেজ ---
@app.route('/')
def index():
    conf = settings_col.find_one({"id": "config"})
    search = request.args.get('s')
    query = {"title": {"$regex": search, "$options": "i"}} if search else {}
    items = list(contents_col.find(query).sort("_id", -1))
    slider = list(contents_col.find().sort("views", -1).limit(int(conf['slider_limit'])))
    cats = list(cat_col.find())
    return render_template_string(USER_HOME_HTML, ui=UI_HEAD, conf=conf, items=items, slider=slider, cats=cats)

# --- ২. ইউজার ডিটেইল পেজ ---
@app.route('/view/<id>')
def view(id):
    item = contents_col.find_one({"_id": ObjectId(id)})
    contents_col.update_one({"_id": ObjectId(id)}, {"$inc": {"views": 1}})
    conf = settings_col.find_one({"id": "config"})
    return render_template_string(USER_DETAIL_HTML, ui=UI_HEAD, m=item, conf=conf)

# --- ৩. অ্যাডমিন কন্ট্রোল প্যানেল (লগইন) ---
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    conf = settings_col.find_one({"id": "config"})
    if request.method == 'POST':
        if request.form.get('u') == conf['admin_user'] and request.form.get('p') == conf['admin_pass']:
            session['admin'] = True
            return redirect('/admin/dashboard')
    return render_template_string(ADMIN_LOGIN_HTML, ui=UI_HEAD)

# --- ৪. অ্যাডমিন ড্যাশবোর্ড (বিভাগসমূহ) ---
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'): return redirect('/admin/login')
    conf = settings_col.find_one({"id": "config"})
    total_content = contents_col.count_documents({})
    return render_template_string(ADMIN_DASHBOARD_HTML, ui=UI_HEAD, conf=conf, total=total_content)

@app.route('/admin/identity', methods=['GET', 'POST'])
def admin_identity():
    if request.method == 'POST':
        settings_col.update_one({"id": "config"}, {"$set": {
            "site_name": request.form.get('name'), "site_logo": request.form.get('logo')
        }})
    return redirect('/admin/dashboard')

@app.route('/admin/notice', methods=['POST'])
def admin_notice():
    settings_col.update_one({"id": "config"}, {"$set": {"header_notice": request.form.get('notice')}})
    return redirect('/admin/dashboard')

@app.route('/admin/limits', methods=['POST'])
def admin_limits():
    settings_col.update_one({"id": "config"}, {"$set": {
        "movie_limit": request.form.get('ml'), "series_limit": request.form.get('sl'), "slider_limit": request.form.get('sll')
    }})
    return redirect('/admin/dashboard')

@app.route('/admin/add_auto', methods=['POST'])
def add_auto():
    tid = request.form.get('tid'); mtype = request.form.get('type')
    api_url = f"https://api.themoviedb.org/3/{mtype}/{tid}?api_key={TMDB_API_KEY}&append_to_response=images"
    d = requests.get(api_url).json()
    logos = d.get('images', {}).get('logos', [])
    logo_url = f"https://image.tmdb.org/t/p/original{logos[0]['file_path']}" if logos else ""
    
    content = {
        "title": d.get("title") or d.get("name"),
        "lang": d.get("original_language", "EN").upper(),
        "year": (d.get("release_date") or d.get("first_air_date", "2024"))[:4],
        "story": d.get("overview"),
        "poster": f"https://image.tmdb.org/t/p/w500{d.get('poster_path')}",
        "backdrop": f"https://image.tmdb.org/t/p/original{d.get('backdrop_path')}",
        "logo": logo_url, "type": mtype, "views": 0, "movie_links": [], "seasons": []
    }
    contents_col.insert_one(content)
    return redirect('/admin/manage')

@app.route('/admin/manage')
def admin_manage():
    q = request.args.get('q', '')
    items = list(contents_col.find({"title": {"$regex": q, "$options": "i"}}).sort("_id", -1))
    return render_template_string(ADMIN_MANAGE_HTML, ui=UI_HEAD, items=items)

@app.route('/admin/delete/<id>')
def delete_item(id):
    contents_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/manage')

@app.route('/admin/cat_manager', methods=['GET', 'POST'])
def cat_manager():
    if request.method == 'POST':
        cat_col.insert_one({"name": request.form.get('cat')})
    return redirect('/admin/dashboard')

@app.route('/admin/cat_del/<id>')
def cat_del(id):
    cat_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/dashboard')

# সিরিজের ইপিসোড ও লিংক অ্যাড
@app.route('/admin/add_episode', methods=['POST'])
def add_episode():
    id = request.form.get('id'); s_num = request.form.get('s'); e_num = request.form.get('e')
    links = []
    raw = request.form.get('links').split(',') # Format: Quality|TG|Direct
    for r in raw:
        p = r.split('|')
        if len(p) == 3: links.append({"q": p[0], "tg": p[1], "d": p[2]})
    
    contents_col.update_one(
        {"_id": ObjectId(id), "seasons.season_num": s_num},
        {"$push": {"seasons.$.episodes": {"ep_num": e_num, "links": links}}}
    ) or contents_col.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"seasons": {"season_num": s_num, "episodes": [{"ep_num": e_num, "links": links}]}}}
    )
    return redirect('/admin/manage')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

# --------------------------------------------------------------------------------------
# HTML TEMPLATES (Inlined for One File)
# --------------------------------------------------------------------------------------

USER_HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <div class="flex items-center gap-4">
            <button onclick="document.getElementById('menu').classList.toggle('hidden')" class="text-xl"><i class="fa fa-bars text-red-600"></i></button>
            <h1 class="text-2xl font-black text-red-600 tracking-tighter cursor-pointer" onclick="location.href='/'">{{ conf.site_name }}</h1>
        </div>
        <form class="bg-gray-900 border border-gray-800 rounded-full px-4 py-1 flex items-center">
            <input name="s" placeholder="Search..." class="bg-transparent text-sm outline-none w-32 md:w-64">
            <button><i class="fa fa-search text-gray-500"></i></button>
        </form>
    </nav>

    <div id="menu" class="hidden fixed inset-0 z-[60]">
        <div class="absolute inset-0 bg-black/80" onclick="this.parentElement.classList.add('hidden')"></div>
        <div class="absolute left-0 top-0 h-full w-72 glass p-8 shadow-2xl">
            <h2 class="text-xl font-bold mb-8 text-red-600 italic">Menu</h2>
            <div class="grid gap-6">
                <a href="/" class="hover:text-red-500"><i class="fa fa-home mr-3"></i> Home</a>
                <div class="text-xs text-gray-600 uppercase font-bold mt-4">Categories</div>
                {% for c in cats %}<a href="/?s={{ c.name }}" class="text-sm hover:text-red-500">{{ c.name }}</a>{% endfor %}
                <hr class="border-gray-800">
                <a href="/admin/login" class="text-xs text-gray-500">Admin Login</a>
            </div>
        </div>
    </div>

    <div class="bg-red-600 text-white text-center py-1 text-[10px] font-bold overflow-hidden"><marquee>{{ conf.header_notice }}</marquee></div>

    <main class="p-4 md:px-16">
        <h2 class="text-xl font-bold mb-4 mt-6 text-red-600 italic uppercase">Trending</h2>
        <div class="flex gap-4 overflow-x-auto no-scrollbar pb-4">
            {% for m in slider %}
            <div class="min-w-[280px] md:min-w-[400px] h-44 md:h-64 relative rounded-3xl overflow-hidden cursor-pointer flex-shrink-0" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover">
                <div class="absolute inset-0 bg-gradient-to-t from-black via-transparent p-6 flex flex-col justify-end">
                    <p class="font-black text-xl">{{ m.title }}</p>
                    <span class="text-xs text-gray-400 font-bold">{{ m.lang }} | {{ m.year }}</span>
                </div>
            </div>
            {% endfor %}
        </div>

        <h2 class="text-2xl font-black mb-8 mt-12 border-l-4 border-red-600 pl-4 italic">LATEST RELEASES</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
            {% for m in items %}
            <div class="cursor-pointer group" onclick="location.href='/view/{{ m._id }}'">
                <div class="relative overflow-hidden rounded-2xl aspect-[2/3] shadow-lg border border-gray-800">
                    <img src="{{ m.poster }}" class="w-full h-full object-cover group-hover:scale-110 transition duration-500">
                    <div class="absolute top-2 right-2 glass px-2 py-1 rounded text-[10px] font-bold text-red-500">{{ m.lang }}</div>
                </div>
                <div class="mt-3">
                    <h3 class="font-bold text-sm truncate">{{ m.title }}</h3>
                    <p class="text-[10px] text-gray-500 uppercase">{{ m.year }} • {{ m.type }}</p>
                </div>
            </div>
            {% endfor %}
        </div>
    </main>
</body>
</html>
"""

USER_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ m.title }}</title></head>
<body>
    <div class="relative h-[50vh] md:h-[70vh]">
        <img src="{{ m.backdrop }}" class="w-full h-full object-cover opacity-30">
        <div class="absolute inset-0 bg-gradient-to-t from-[#05070a] via-transparent"></div>
        <button onclick="history.back()" class="absolute top-6 left-6 glass h-12 w-12 rounded-full flex items-center justify-center"><i class="fa fa-arrow-left"></i></button>
        <div class="absolute bottom-10 left-6 md:left-20">
            {% if m.logo %}<img src="{{ m.logo }}" class="w-64 md:w-96 mb-6">
            {% else %}<h1 class="text-4xl md:text-6xl font-black italic mb-4 tracking-tighter uppercase">{{ m.title }}</h1>{% endif %}
            <div class="flex gap-4 text-xs font-bold text-gray-500 items-center uppercase tracking-widest">
                <span class="bg-red-600 text-white px-2 py-1 rounded">Premium</span>
                <span>{{ m.year }}</span>
                <span>{{ m.lang }}</span>
                <span><i class="fa fa-eye"></i> {{ m.views }}</span>
            </div>
        </div>
    </div>

    <div class="p-6 md:p-20">
        <p class="text-gray-400 max-w-4xl text-sm md:text-lg mb-10 leading-relaxed">{{ m.story }}</p>
        
        {% if m.type == 'movie' %}
            <h3 class="text-xl font-bold mb-6 italic border-l-4 border-red-600 pl-3">WATCH & DOWNLOAD</h3>
            <div class="grid gap-3 max-w-2xl">
                {% for l in m.movie_links %}
                <div class="glass p-4 rounded-xl flex justify-between items-center">
                    <div class="font-bold text-red-500 italic">{{ l.quality }}</div>
                    <div class="flex gap-2">
                        <a href="{{ l.tg }}" class="text-sky-500 p-2"><i class="fab fa-telegram text-xl"></i></a>
                        <a href="{{ l.direct }}" class="bg-white text-black px-4 py-1.5 rounded-full text-[10px] font-black italic">DOWNLOAD</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <h3 class="text-xl font-bold mb-6 italic border-l-4 border-red-600 pl-3 uppercase">Seasons</h3>
            <div class="flex gap-4 overflow-x-auto no-scrollbar border-b border-gray-900 mb-8 pb-2">
                {% for s in m.seasons %}
                <button onclick="showS('{{ s.season_num }}')" class="tab-btn px-6 py-2 uppercase font-black italic tracking-tighter" id="t-{{ s.season_num }}">S-{{ s.season_num }}</button>
                {% endfor %}
            </div>
            {% for s in m.seasons %}
            <div class="s-content hidden grid gap-4" id="s-{{ s.season_num }}">
                {% for ep in s.episodes %}
                <div class="glass p-6 rounded-3xl">
                    <div class="text-gray-500 font-bold text-xs uppercase mb-4 tracking-widest">Episode {{ ep.ep_num }}</div>
                    <div class="grid md:grid-cols-2 gap-3">
                        {% for link in ep.links %}
                        <div class="bg-gray-800/50 p-4 rounded-2xl flex justify-between items-center">
                            <span class="text-red-500 font-black text-xs">{{ link.q }}</span>
                            <div class="flex gap-3">
                                <a href="{{ link.tg }}" class="text-sky-500"><i class="fab fa-telegram"></i></a>
                                <a href="{{ link.d }}" class="bg-white text-black px-4 py-1 rounded-full text-[9px] font-black uppercase">Get Link</a>
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
        function showS(n) {
            document.querySelectorAll('.s-content').forEach(c => c.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('tab-active'));
            document.getElementById('s-'+n).classList.remove('hidden');
            document.getElementById('t-'+n).classList.add('tab-active');
        }
        window.onload = () => { if(document.querySelector('.tab-btn')) document.querySelector('.tab-btn').click(); }
    </script>
</body>
</html>
"""

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Mega Panel</title></head>
<body class="flex flex-col md:flex-row">
    <!-- Sidebar / Menus -->
    <div class="w-full md:w-80 h-screen glass sticky top-0 p-8 overflow-y-auto">
        <h2 class="text-red-600 font-black text-3xl italic mb-10 tracking-tighter">MEGA ADMIN</h2>
        <div class="grid gap-6 text-sm font-bold">
            <a href="/admin/dashboard" class="text-red-500"><i class="fa fa-home mr-3"></i> Dashboard Overview</a>
            <a href="/admin/manage"><i class="fa fa-tasks mr-3"></i> Content Management</a>
            <hr class="border-gray-800">
            <div class="text-[10px] text-gray-600 uppercase tracking-widest font-black">Quick Settings</div>
            <a href="#identity" onclick="toggleMenu('identity')"><i class="fa fa-id-card mr-3"></i> Site Identity (Name/Logo)</a>
            <a href="#notice" onclick="toggleMenu('notice')"><i class="fa fa-bullhorn mr-3"></i> Header Notice</a>
            <a href="#limits" onclick="toggleMenu('limits')"><i class="fa fa-sliders mr-3"></i> Home Limits</a>
            <a href="#cats" onclick="toggleMenu('cats')"><i class="fa fa-tags mr-3"></i> Category Manager</a>
            <a href="/admin/manage"><i class="fa fa-search mr-3"></i> Search & Edit Content</a>
            <a href="/logout" class="mt-20 text-red-900 italic">Terminate Session</a>
        </div>
    </div>

    <!-- Main Dynamic Content -->
    <div class="flex-1 p-6 md:p-12 overflow-y-auto">
        <h2 class="text-3xl font-black mb-10 italic">DASHBOARD OVERVIEW</h2>
        <div class="grid md:grid-cols-3 gap-6 mb-12">
            <div class="admin-card text-center"><p class="text-gray-500 text-xs">Total Dramas/Movies</p><h3 class="text-4xl font-black text-red-600">{{ total }}</h3></div>
            <div class="admin-card text-center"><p class="text-gray-500 text-xs">Active Theme</p><h3 class="text-xl font-bold">Premium Dark</h3></div>
            <div class="admin-card text-center"><p class="text-gray-500 text-xs">System Status</p><h3 class="text-xl font-bold text-green-500">Live</h3></div>
        </div>

        <div id="identity" class="admin-card mb-8">
            <h3 class="font-black mb-4">🌐 SITE IDENTITY</h3>
            <form action="/admin/identity" method="POST" class="grid gap-4">
                <input name="name" value="{{ conf.site_name }}" class="input-field" placeholder="Site Name">
                <input name="logo" value="{{ conf.site_logo }}" class="input-field" placeholder="Logo PNG URL">
                <button class="btn-red">Update Identity</button>
            </form>
        </div>

        <div id="notice" class="admin-card mb-8">
            <h3 class="font-black mb-4">📢 HEADER NOTICE</h3>
            <form action="/admin/notice" method="POST" class="grid gap-4">
                <textarea name="notice" class="input-field">{{ conf.header_notice }}</textarea>
                <button class="btn-red">Update Notice</button>
            </form>
        </div>

        <div id="limits" class="admin-card mb-8">
            <h3 class="font-black mb-4">📊 HOME LIMITS</h3>
            <form action="/admin/limits" method="POST" class="grid md:grid-cols-3 gap-4">
                <input name="ml" value="{{ conf.movie_limit }}" class="input-field" placeholder="Movie Limit">
                <input name="sl" value="{{ conf.series_limit }}" class="input-field" placeholder="Series Limit">
                <input name="sll" value="{{ conf.slider_limit }}" class="input-field" placeholder="Slider Limit">
                <button class="btn-red md:col-span-3">Save All Limits</button>
            </form>
        </div>

        <div id="cats" class="admin-card mb-8">
            <h3 class="font-black mb-4">📁 CATEGORY MANAGER</h3>
            <form action="/admin/cat_manager" method="POST" class="flex gap-2 mb-4">
                <input name="cat" class="input-field" placeholder="Add New Category">
                <button class="btn-red">ADD</button>
            </form>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                {% for c in cats %}<div class="bg-gray-800 p-2 rounded flex justify-between text-xs">{{ c.name }} <a href="/admin/cat_del/{{ c._id }}" class="text-red-500">X</a></div>{% endfor %}
            </div>
        </div>

        <div class="admin-card mb-8 bg-red-600/5 border-red-600/20">
            <h3 class="font-black mb-4">➕ ADD NEW CONTENT (TMDB AUTO)</h3>
            <form action="/admin/add_auto" method="POST" class="flex gap-2">
                <select name="type" class="input-field w-32"><option value="movie">Movie</option><option value="tv">TV Series</option></select>
                <input name="tid" class="input-field flex-1" placeholder="Enter TMDB ID (e.g. 550)">
                <button class="btn-red">AUTO FETCH & SAVE</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

ADMIN_MANAGE_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Manage Content</title></head>
<body class="p-8">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-4xl font-black italic tracking-tighter"><i class="fa fa-tasks text-red-600 mr-4"></i> MANAGE CONTENT</h2>
            <a href="/admin/dashboard" class="text-red-500 font-bold"><i class="fa fa-arrow-left"></i> BACK</a>
        </div>

        <form class="flex gap-2 mb-10">
            <input name="q" class="input-field flex-1" placeholder="Search dramas or movies to edit/delete...">
            <button class="btn-red">SEARCH</button>
        </form>

        <div class="grid gap-6">
            {% for m in items %}
            <div class="admin-card flex flex-col md:flex-row justify-between items-center gap-6">
                <div class="flex items-center gap-6">
                    <img src="{{ m.poster }}" class="h-20 w-16 rounded-xl object-cover border border-gray-800">
                    <div>
                        <h4 class="text-xl font-bold italic">{{ m.title }}</h4>
                        <span class="text-[10px] text-gray-500 uppercase font-bold">{{ m.type }} | {{ m.year }} | {{ m.views }} Views</span>
                    </div>
                </div>

                <div class="flex-1 w-full md:w-auto">
                    {% if m.type == 'tv' %}
                    <form action="/admin/add_episode" method="POST" class="grid grid-cols-2 md:grid-cols-4 gap-2">
                        <input type="hidden" name="id" value="{{ m._id }}">
                        <input name="s" placeholder="Season" class="input-field text-xs p-1">
                        <input name="e" placeholder="Episode" class="input-field text-xs p-1">
                        <input name="links" placeholder="Q|TG|Direct" class="input-field text-xs p-1">
                        <button class="bg-indigo-600 text-[10px] font-black rounded uppercase">Add EP</button>
                    </form>
                    {% else %}
                    <p class="text-xs text-gray-600 italic">Movie links are added via same structure (Logic placeholder)</p>
                    {% endif %}
                </div>

                <a href="/admin/delete/{{ m._id }}" class="text-red-900 font-bold text-xs uppercase" onclick="return confirm('Delete?')">Delete</a>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Gate</title></head>
<body class="flex items-center justify-center min-h-screen p-6">
    <div class="glass p-10 md:p-16 rounded-[40px] w-full max-w-lg shadow-2xl">
        <h2 class="text-4xl font-black mb-10 text-center italic text-red-600 tracking-tighter">ADMIN GATE</h2>
        <form method="POST" class="grid gap-6">
            <input name="u" placeholder="Admin Username" class="input-field text-center text-lg" required>
            <input name="p" type="password" placeholder="Passcode" class="input-field text-center text-lg" required>
            <button class="w-full btn-red py-4 rounded-2xl text-xl font-black mt-4 shadow-xl shadow-red-900/20">UNSEAL ACCESS</button>
        </form>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
