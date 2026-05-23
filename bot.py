import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "ULTIMATE_DRAMA_STORE_FIXED_FINAL"

# --- ডাটাবেজ এবং API কনফিগারেশন ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['DramaStoreDB']
contents_col = db['contents']
settings_col = db['site_settings']
cat_col = db['categories']

# ডিফল্ট সেটিংস চেক
if not settings_col.find_one({"id": "config"}):
    settings_col.insert_one({
        "id": "config", "site_name": "DRAMA-FLIX", "site_logo": "https://i.ibb.co/logo.png",
        "header_notice": "Welcome to Premium Drama Store", "admin_user": "admin", "admin_pass": "1234",
        "movie_limit": 20, "series_limit": 20, "slider_limit": 10
    })

# --- UI STYLES (Ultra Premium Responsive) ---
UI_HEAD = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;900&display=swap');
    :root { --p: #e50914; --bg: #05070a; }
    body { background: var(--bg); color: #f8fafc; font-family: 'Inter', sans-serif; }
    .glass { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(15px); border: 1px solid rgba(255,255,255,0.05); }
    .btn-red { background: var(--p); color: white; border-radius: 8px; font-weight: bold; transition: 0.3s; padding: 10px 20px; text-align: center; cursor: pointer; }
    .btn-red:hover { background: #b20710; transform: scale(1.02); }
    .input-field { background: #0f172a; border: 1px solid #1e293b; color: white; padding: 12px; border-radius: 12px; width: 100%; outline: none; }
    .input-field:focus { border-color: var(--p); }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .tab-active { border-bottom: 4px solid var(--p); color: var(--p); font-weight: 900; }
    .admin-sidebar a { display: flex; align-items: center; padding: 12px; border-radius: 10px; color: #94a3b8; transition: 0.2s; }
    .admin-sidebar a:hover, .admin-sidebar a.active { background: #1e293b; color: white; }
</style>
"""

# -----------------------------------------------------------
# CORE ROUTES (User Side)
# -----------------------------------------------------------

@app.route('/')
def index():
    conf = settings_col.find_one({"id": "config"})
    search = request.args.get('s')
    query = {"title": {"$regex": search, "$options": "i"}} if search else {}
    items = list(contents_col.find(query).sort("_id", -1))
    slider = list(contents_col.find().sort("views", -1).limit(int(conf['slider_limit'])))
    cats = list(cat_col.find())
    return render_template_string(USER_HOME_HTML, ui=UI_HEAD, conf=conf, items=items, slider=slider, cats=cats)

@app.route('/view/<id>')
def view(id):
    item = contents_col.find_one({"_id": ObjectId(id)})
    contents_col.update_one({"_id": ObjectId(id)}, {"$inc": {"views": 1}})
    return render_template_string(USER_DETAIL_HTML, ui=UI_HEAD, m=item, conf=settings_col.find_one({"id": "config"}))

# -----------------------------------------------------------
# ADMIN ROUTES (Mega Control Panel)
# -----------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        c = settings_col.find_one({"id": "config"})
        if request.form.get('u') == c['admin_user'] and request.form.get('p') == c['admin_pass']:
            session['admin'] = True; return redirect('/admin/dashboard')
    return render_template_string(ADMIN_LOGIN_HTML, ui=UI_HEAD)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'): return redirect('/admin/login')
    conf = settings_col.find_one({"id": "config"})
    cats = list(cat_col.find())
    stats = {"total": contents_col.count_documents({}), "movie": contents_col.count_documents({"type":"movie"}), "tv": contents_col.count_documents({"type":"tv"})}
    return render_template_string(ADMIN_DASHBOARD_HTML, ui=UI_HEAD, conf=conf, cats=cats, stats=stats)

# TMDB Auto Fetch API
@app.route('/api/tmdb_search')
def api_tmdb_search():
    q = request.args.get('q'); t = request.args.get('t', 'movie')
    url = f"https://api.themoviedb.org/3/search/{t}?api_key={TMDB_API_KEY}&query={q}"
    return jsonify(requests.get(url).json())

@app.route('/api/tmdb_info')
def api_tmdb_info():
    tid = request.args.get('id'); t = request.args.get('t')
    url = f"https://api.themoviedb.org/3/{t}/{tid}?api_key={TMDB_API_KEY}&append_to_response=images"
    res = requests.get(url).json()
    logos = res.get('images', {}).get('logos', [])
    logo = f"https://image.tmdb.org/t/p/original{logos[0]['file_path']}" if logos else ""
    return jsonify({"data": res, "logo": logo})

# Save/Edit Content
@app.route('/admin/save', methods=['POST'])
def admin_save():
    cid = request.form.get('cid')
    data = {
        "title": request.form.get('title'), "lang": request.form.get('lang'),
        "year": request.form.get('year'), "story": request.form.get('story'),
        "poster": request.form.get('poster'), "backdrop": request.form.get('backdrop'),
        "logo": request.form.get('logo'), "type": request.form.get('type'),
        "category": request.form.getlist('cats')
    }
    if cid:
        contents_col.update_one({"_id": ObjectId(cid)}, {"$set": data})
    else:
        data["views"] = 0; data["movie_links"] = []; data["seasons"] = []
        contents_col.insert_one(data)
    return redirect('/admin/manage')

@app.route('/admin/manage')
def admin_manage():
    if not session.get('admin'): return redirect('/admin/login')
    q = request.args.get('q', '')
    items = list(contents_col.find({"title": {"$regex": q, "$options": "i"}}).sort("_id", -1))
    return render_template_string(ADMIN_MANAGE_HTML, ui=UI_HEAD, items=items)

# Manage Movie Links
@app.route('/admin/links/<id>', methods=['GET', 'POST'])
def manage_links(id):
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            link = {"id": str(ObjectId()), "q": request.form.get('q'), "tg": request.form.get('tg'), "d": request.form.get('d')}
            contents_col.update_one({"_id": ObjectId(id)}, {"$push": {"movie_links": link}})
        elif action == 'delete':
            lid = request.form.get('lid')
            contents_col.update_one({"_id": ObjectId(id)}, {"$pull": {"movie_links": {"id": lid}}})
    item = contents_col.find_one({"_id": ObjectId(id)})
    return render_template_string(ADMIN_LINKS_HTML, ui=UI_HEAD, m=item)

# Manage Seasons & Episodes
@app.route('/admin/series/<id>', methods=['GET', 'POST'])
def manage_series(id):
    if request.method == 'POST':
        action = request.form.get('action')
        sn = request.form.get('sn')
        if action == 'add_ep':
            ep = {
                "id": str(ObjectId()), "en": request.form.get('en'),
                "links": [{"q": x.split('|')[0], "tg": x.split('|')[1], "d": x.split('|')[2]} for x in request.form.get('links').split(',') if '|' in x]
            }
            res = contents_col.update_one({"_id": ObjectId(id), "seasons.sn": sn}, {"$push": {"seasons.$.eps": ep}})
            if res.matched_count == 0:
                contents_col.update_one({"_id": ObjectId(id)}, {"$push": {"seasons": {"sn": sn, "eps": [ep]}}})
        elif action == 'del_ep':
            eid = request.form.get('eid')
            contents_col.update_one({"_id": ObjectId(id), "seasons.sn": sn}, {"$pull": {"seasons.$.eps": {"id": eid}}})
    item = contents_col.find_one({"_id": ObjectId(id)})
    return render_template_string(ADMIN_SERIES_HTML, ui=UI_HEAD, m=item)

# Settings Update
@app.route('/admin/settings', methods=['POST'])
def admin_settings():
    settings_col.update_one({"id": "config"}, {"$set": request.form.to_dict()})
    return redirect('/admin/dashboard')

@app.route('/admin/cat/add', methods=['POST'])
def cat_add(): cat_col.insert_one({"name": request.form.get('name')}); return redirect('/admin/dashboard')

@app.route('/admin/delete/<id>')
def admin_delete(id): contents_col.delete_one({"_id": ObjectId(id)}); return redirect('/admin/manage')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

# --------------------------------------------------------------------------------------
# HTML TEMPLATES (Inlined)
# --------------------------------------------------------------------------------------

USER_HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <div class="flex items-center gap-4">
            <button onclick="document.getElementById('side').classList.toggle('hidden')" class="text-xl"><i class="fa fa-bars text-red-600"></i></button>
            <h1 class="text-2xl font-black text-red-600 italic tracking-tighter" onclick="location.href='/'">{{ conf.site_name }}</h1>
        </div>
        <form class="hidden md:flex bg-gray-900/50 border border-gray-800 rounded-full px-4 py-1 items-center">
            <input name="s" placeholder="Search..." class="bg-transparent text-sm outline-none w-64">
            <button><i class="fa fa-search text-gray-500"></i></button>
        </form>
    </nav>
    <div id="side" class="hidden fixed inset-0 z-[60]">
        <div class="absolute inset-0 bg-black/90" onclick="this.parentElement.classList.add('hidden')"></div>
        <div class="absolute left-0 top-0 h-full w-80 glass p-10">
            <h2 class="text-2xl font-black text-red-600 mb-10 italic">MENU</h2>
            <div class="grid gap-6">
                <a href="/"><i class="fa fa-home mr-3"></i> Home</a>
                <div class="text-[10px] text-gray-600 uppercase font-black mt-4">Categories</div>
                {% for c in cats %}<a href="/?s={{ c.name }}" class="text-sm hover:text-red-500">{{ c.name }}</a>{% endfor %}
                <hr class="border-gray-800">
                <a href="/admin/login" class="text-xs text-gray-500">Admin Access</a>
            </div>
        </div>
    </div>
    <div class="bg-red-600 text-white text-center py-1 text-[10px] font-black uppercase overflow-hidden"><marquee>{{ conf.header_notice }}</marquee></div>
    <main class="p-4 md:px-16">
        <div class="flex gap-4 overflow-x-auto no-scrollbar py-6">
            {% for m in slider %}
            <div class="min-w-[300px] md:min-w-[450px] h-44 md:h-64 relative rounded-[30px] overflow-hidden flex-shrink-0 cursor-pointer" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover">
                <div class="absolute inset-0 bg-gradient-to-t from-black via-transparent p-6 flex flex-col justify-end">
                    <p class="font-black text-xl uppercase tracking-tighter">{{ m.title }}</p>
                    <span class="text-xs text-gray-400 font-bold uppercase">{{ m.year }} • {{ m.lang }}</span>
                </div>
            </div>
            {% endfor %}
        </div>
        <h2 class="text-2xl font-black mb-8 mt-12 border-l-8 border-red-600 pl-4 italic tracking-tighter uppercase">Recommended For You</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
            {% for m in items %}
            <div class="cursor-pointer group" onclick="location.href='/view/{{ m._id }}'">
                <div class="relative rounded-2xl overflow-hidden aspect-[2/3] border border-gray-800 shadow-2xl">
                    <img src="{{ m.poster }}" class="w-full h-full object-cover group-hover:scale-110 transition duration-500">
                    <div class="absolute top-2 right-2 glass px-2 py-1 rounded text-[10px] font-bold text-red-500">{{ m.lang }}</div>
                </div>
                <div class="mt-3 px-1">
                    <h3 class="font-bold text-sm truncate uppercase group-hover:text-red-500 transition">{{ m.title }}</h3>
                    <p class="text-[10px] text-gray-500 font-bold uppercase">{{ m.year }}</p>
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
    <div class="relative h-[60vh] md:h-[80vh]">
        <img src="{{ m.backdrop }}" class="w-full h-full object-cover opacity-30">
        <div class="absolute inset-0 bg-gradient-to-t from-[#05070a] via-transparent"></div>
        <button onclick="history.back()" class="absolute top-8 left-8 glass h-12 w-12 rounded-full flex items-center justify-center"><i class="fa fa-arrow-left"></i></button>
        <div class="absolute bottom-12 left-6 md:left-20">
            {% if m.logo %}<img src="{{ m.logo }}" class="w-64 md:w-96 mb-6">
            {% else %}<h1 class="text-5xl md:text-8xl font-black italic tracking-tighter uppercase mb-4">{{ m.title }}</h1>{% endif %}
            <div class="flex gap-4 text-xs font-black text-gray-400 items-center uppercase tracking-widest">
                <span class="bg-red-600 text-white px-2 py-1 rounded">ULTRA HD</span>
                <span>{{ m.year }}</span>
                <span>{{ m.lang }}</span>
                <span><i class="fa fa-eye"></i> {{ m.views }}</span>
            </div>
            <p class="text-gray-300 text-sm md:text-lg max-w-4xl line-clamp-3 md:line-clamp-none italic mt-4">{{ m.story }}</p>
        </div>
    </div>
    <div class="p-6 md:p-20">
        {% if m.type == 'movie' %}
            <h3 class="text-2xl font-black mb-8 italic border-l-4 border-red-600 pl-4 uppercase">Watch Now</h3>
            <div class="grid gap-4 max-w-3xl">
                {% for l in m.movie_links %}
                <div class="glass p-5 rounded-2xl flex justify-between items-center">
                    <span class="font-black text-red-600 italic tracking-widest">{{ l.q }}</span>
                    <div class="flex gap-4">
                        <a href="{{ l.tg }}" class="text-sky-500"><i class="fab fa-telegram text-2xl"></i></a>
                        <a href="{{ l.d }}" class="bg-white text-black px-6 py-2 rounded-xl font-black text-[10px] uppercase italic">Download</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <div class="flex gap-6 border-b border-gray-900 mb-10 overflow-x-auto no-scrollbar">
                {% for s in m.seasons %}
                <button onclick="showS('{{ s.sn }}')" class="s-tab px-6 py-4 uppercase font-black italic tracking-tighter" id="btn-{{ s.sn }}">Season {{ s.sn }}</button>
                {% endfor %}
            </div>
            {% for s in m.seasons %}
            <div class="s-content hidden grid gap-6" id="box-{{ s.sn }}">
                {% for ep in s.eps %}
                <div class="glass p-8 rounded-[40px]">
                    <div class="font-black text-[10px] text-gray-500 uppercase mb-4 tracking-widest">Episode {{ ep.en }}</div>
                    <div class="grid md:grid-cols-2 gap-4">
                        {% for l in ep.links %}
                        <div class="bg-gray-800/30 p-4 rounded-2xl flex justify-between items-center border border-white/5">
                            <span class="text-red-500 font-black italic text-xs">{{ l.q }}</span>
                            <div class="flex gap-4">
                                <a href="{{ l.tg }}" class="text-sky-500"><i class="fab fa-telegram"></i></a>
                                <a href="{{ l.d }}" class="bg-white text-black px-4 py-1 rounded-full text-[8px] font-black uppercase">Get Link</a>
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
        function showS(n){
            document.querySelectorAll('.s-content').forEach(c => c.classList.add('hidden'));
            document.querySelectorAll('.s-tab').forEach(t => t.classList.remove('tab-active'));
            document.getElementById('box-'+n).classList.remove('hidden');
            document.getElementById('btn-'+n).classList.add('tab-active');
        }
        window.onload = () => { if(document.querySelector('.s-tab')) document.querySelector('.s-tab').click(); }
    </script>
</body>
</html>
"""

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Mega Dashboard</title></head>
<body class="flex flex-col md:flex-row min-h-screen">
    <div class="w-full md:w-80 h-screen glass sticky top-0 p-8 admin-sidebar overflow-y-auto">
        <h2 class="text-red-600 font-black text-3xl italic mb-12 tracking-tighter">ADMIN BOX</h2>
        <a href="/admin/dashboard" class="active"><i class="fa fa-home mr-3"></i> Dashboard</a>
        <a href="/admin/manage"><i class="fa fa-tasks mr-3"></i> Manage Content</a>
        <a href="/logout" class="mt-20 text-red-900"><i class="fa fa-sign-out mr-3"></i> Logout</a>
    </div>
    <div class="flex-1 p-6 md:p-12 space-y-10">
        <div class="grid md:grid-cols-3 gap-6">
            <div class="glass p-8 rounded-3xl text-center"><p class="text-[10px] uppercase font-black text-gray-500">Total Items</p><h3 class="text-5xl font-black text-red-600">{{ stats.total }}</h3></div>
            <div class="glass p-8 rounded-3xl text-center"><p class="text-[10px] uppercase font-black text-gray-500">Movies</p><h3 class="text-5xl font-black">{{ stats.movie }}</h3></div>
            <div class="glass p-8 rounded-3xl text-center"><p class="text-[10px] uppercase font-black text-gray-500">Series</p><h3 class="text-5xl font-black">{{ stats.tv }}</h3></div>
        </div>

        <!-- 1. AUTO SEARCH & ADD -->
        <div class="glass p-10 rounded-[40px] border-red-600/20">
            <h3 class="text-xl font-black mb-6 text-red-600 italic uppercase">Auto Fetch (TMDB Mode)</h3>
            <div class="flex gap-4">
                <select id="tmdb_type" class="input-field w-32"><option value="movie">Movie</option><option value="tv">TV Series</option></select>
                <input id="tmdb_q" placeholder="Enter Movie/Series Name..." class="input-field flex-1">
                <button onclick="searchTMDB()" class="btn-red px-10">SEARCH</button>
            </div>
            <div id="results" class="flex gap-4 overflow-x-auto no-scrollbar py-6"></div>
        </div>

        <!-- 2. EDIT FORM -->
        <form action="/admin/save" method="POST" class="glass p-10 rounded-[40px] grid md:grid-cols-2 gap-8">
            <input type="hidden" name="cid" id="f_cid">
            <input type="hidden" name="type" id="f_type">
            <div>
                <label class="text-[10px] font-black uppercase text-gray-500 ml-2">Main Title</label>
                <input name="title" id="f_title" class="input-field mb-4" required>
                <div class="grid grid-cols-2 gap-4">
                    <input name="year" id="f_year" placeholder="Year" class="input-field">
                    <input name="lang" id="f_lang" placeholder="Lang" class="input-field">
                </div>
                <label class="text-[10px] font-black uppercase text-gray-500 mt-4 block ml-2">Images & Logo</label>
                <input name="poster" id="f_poster" placeholder="Poster URL" class="input-field mb-2">
                <input name="backdrop" id="f_backdrop" placeholder="Backdrop URL" class="input-field mb-2">
                <input name="logo" id="f_logo" placeholder="Logo PNG URL" class="input-field">
            </div>
            <div>
                <label class="text-[10px] font-black uppercase text-gray-500 ml-2">Categories</label>
                <div class="grid grid-cols-2 gap-2 bg-black/40 p-4 rounded-2xl border border-gray-800 h-28 overflow-y-auto mb-4">
                    {% for c in cats %}<label class="text-xs"><input type="checkbox" name="cats" value="{{ c.name }}"> {{ c.name }}</label>{% endfor %}
                </div>
                <label class="text-[10px] font-black uppercase text-gray-500 ml-2">Storyline</label>
                <textarea name="story" id="f_story" class="input-field h-32"></textarea>
                <button class="w-full btn-red py-4 rounded-3xl font-black text-xl mt-6 italic tracking-widest">SAVE / UPDATE CONTENT</button>
            </div>
        </form>

        <!-- 3. QUICK SETTINGS -->
        <div class="glass p-10 rounded-[40px]">
            <h3 class="text-xl font-black mb-6 text-red-600 italic uppercase tracking-tighter">Site Settings</h3>
            <form action="/admin/settings" method="POST" class="grid md:grid-cols-2 gap-6">
                <input name="site_name" value="{{ conf.site_name }}" class="input-field" placeholder="Site Name">
                <input name="site_logo" value="{{ conf.site_logo }}" class="input-field" placeholder="Site Logo URL">
                <textarea name="header_notice" class="input-field md:col-span-2">{{ conf.header_notice }}</textarea>
                <button class="btn-red md:col-span-2">Update Configuration</button>
            </form>
        </div>
    </div>
    <script>
        async function searchTMDB(){
            const q = document.getElementById('tmdb_q').value;
            const t = document.getElementById('tmdb_type').value;
            const res = await fetch(`/api/tmdb_search?q=${q}&t=${t}`);
            const data = await res.json();
            const div = document.getElementById('results');
            div.innerHTML = '';
            data.results.forEach(m => {
                div.innerHTML += `<div class="min-w-[120px] cursor-pointer" onclick="fill('${m.id}', '${t}')"><img src="https://image.tmdb.org/t/p/w200${m.poster_path}" class="rounded-xl border-2 border-transparent hover:border-red-600 transition"></div>`;
            });
        }
        async function fill(id, type){
            const res = await fetch(`/api/tmdb_info?id=${id}&t=${type}`);
            const j = await res.json(); const d = j.data;
            document.getElementById('f_cid').value = ''; // Reset ID for new add
            document.getElementById('f_title').value = d.title || d.name;
            document.getElementById('f_year').value = (d.release_date || d.first_air_date).split('-')[0];
            document.getElementById('f_lang').value = d.original_language.toUpperCase();
            document.getElementById('f_poster').value = 'https://image.tmdb.org/t/p/w500' + d.poster_path;
            document.getElementById('f_backdrop').value = 'https://image.tmdb.org/t/p/original' + d.backdrop_path;
            document.getElementById('f_logo').value = j.logo;
            document.getElementById('f_story').value = d.overview;
            document.getElementById('f_type').value = type;
            alert("Data Loaded! Verify and Save.");
        }
    </script>
</body>
</html>
"""

ADMIN_MANAGE_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Management</title></head>
<body class="p-10">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-12">
            <h2 class="text-4xl font-black italic uppercase tracking-tighter">Content Hub</h2>
            <a href="/admin/dashboard" class="btn-red text-xs">Back</a>
        </div>
        <div class="space-y-6">
            {% for m in items %}
            <div class="glass p-6 rounded-[40px] flex items-center justify-between gap-6">
                <div class="flex items-center gap-6">
                    <img src="{{ m.poster }}" class="h-20 w-16 rounded-xl object-cover">
                    <div>
                        <h4 class="text-xl font-black italic">{{ m.title }}</h4>
                        <span class="text-xs font-bold text-gray-500 uppercase">{{ m.type }} | {{ m.year }}</span>
                    </div>
                </div>
                <div class="flex gap-4">
                    {% if m.type == 'movie' %}
                    <a href="/admin/links/{{ m._id }}" class="bg-blue-600 px-6 py-2 rounded-xl text-xs font-black uppercase italic">Links</a>
                    {% else %}
                    <a href="/admin/series/{{ m._id }}" class="bg-indigo-600 px-6 py-2 rounded-xl text-xs font-black uppercase italic">Episodes</a>
                    {% endif %}
                    <a href="/admin/delete/{{ m._id }}" class="bg-red-900 px-6 py-2 rounded-xl text-xs font-black uppercase" onclick="return confirm('Delete?')">Kill</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

ADMIN_LINKS_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Movie Links</title></head>
<body class="p-10 bg-gray-950">
    <div class="max-w-4xl mx-auto glass p-10 rounded-[50px]">
        <h2 class="text-3xl font-black mb-8 italic uppercase tracking-tighter">Links: {{ m.title }}</h2>
        <form method="POST" class="grid grid-cols-4 gap-4 mb-10">
            <input type="hidden" name="action" value="add">
            <input name="q" placeholder="Quality" class="input-field">
            <input name="tg" placeholder="TG Link" class="input-field">
            <input name="d" placeholder="Direct Link" class="input-field">
            <button class="btn-red">Add Link</button>
        </form>
        <div class="space-y-3">
            {% for l in m.movie_links %}
            <form method="POST" class="bg-black/40 p-4 rounded-2xl flex justify-between items-center border border-white/5">
                <input type="hidden" name="action" value="delete">
                <input type="hidden" name="lid" value="{{ l.id }}">
                <span class="font-black text-red-600 uppercase italic">{{ l.q }}</span>
                <button class="text-red-900 text-xs font-black uppercase">Remove</button>
            </form>
            {% endfor %}
        </div>
        <a href="/admin/manage" class="block mt-10 text-center text-gray-500 text-xs">Back to Hub</a>
    </div>
</body>
</html>
"""

ADMIN_SERIES_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Series Manager</title></head>
<body class="p-10">
    <div class="max-w-5xl mx-auto glass p-10 rounded-[50px]">
        <h2 class="text-3xl font-black mb-10 italic uppercase tracking-tighter">Seasons: {{ m.title }}</h2>
        <form method="POST" class="grid md:grid-cols-4 gap-4 mb-12 bg-white/5 p-8 rounded-3xl">
            <input type="hidden" name="action" value="add_ep">
            <input name="sn" placeholder="Season No" class="input-field" required>
            <input name="en" placeholder="Episode No" class="input-field" required>
            <input name="links" placeholder="Format: Quality|TG|Direct, Q2|TG2|D2" class="input-field col-span-1 md:col-span-2" required>
            <button class="btn-red md:col-span-4">ADD EPISODE</button>
        </form>

        {% for s in m.seasons %}
        <div class="mb-10">
            <h3 class="text-xl font-black text-red-600 mb-6 italic">Season {{ s.sn }}</h3>
            <div class="space-y-4">
                {% for ep in s.eps %}
                <form method="POST" class="glass p-6 rounded-3xl flex justify-between items-center border-l-4 border-indigo-600">
                    <input type="hidden" name="action" value="del_ep">
                    <input type="hidden" name="sn" value="{{ s.sn }}">
                    <input type="hidden" name="eid" value="{{ ep.id }}">
                    <div>
                        <div class="font-black uppercase tracking-widest text-xs">Episode {{ ep.en }}</div>
                        <div class="flex gap-2 mt-1">
                            {% for link in ep.links %}<span class="text-[8px] bg-white/5 px-2 py-0.5 rounded text-gray-500">{{ link.q }}</span>{% endfor %}
                        </div>
                    </div>
                    <button class="text-red-900 text-[10px] font-black uppercase">Delete Ep</button>
                </form>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
        <a href="/admin/manage" class="block text-center text-gray-600 text-xs mt-10">Return to Hub</a>
    </div>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Gate</title></head>
<body class="flex items-center justify-center min-h-screen">
    <form method="POST" class="glass p-16 rounded-[60px] w-full max-w-lg shadow-2xl text-center">
        <h2 class="text-5xl font-black text-red-600 italic tracking-tighter mb-10 uppercase">Admin Gate</h2>
        <input name="u" placeholder="Admin Username" class="input-field text-center text-lg mb-6" required>
        <input name="p" type="password" placeholder="Passcode" class="input-field text-center text-lg mb-8" required>
        <button class="w-full btn-red py-5 rounded-3xl text-xl font-black uppercase tracking-widest shadow-2xl shadow-red-900/30">Unseal Access</button>
    </form>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
