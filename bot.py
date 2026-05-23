import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "ULTIMATE_DRAMA_STORE_2024_PREMIUM"

# --- CONFIGURATION (Your Provided Data) ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['DramaStoreDB']
contents_col = db['contents']
settings_col = db['site_settings']
cat_col = db['categories']

# Initialize Default Mega Settings
if not settings_col.find_one({"id": "config"}):
    settings_col.insert_one({
        "id": "config",
        "site_name": "DRAMA STORE",
        "site_logo": "https://i.ibb.co/logo.png",
        "site_favicon": "https://i.ibb.co/fav.png",
        "header_notice": "Welcome to the world of Premium Dramas and Movies!",
        "admin_user": "admin",
        "admin_pass": "1234",
        "movie_limit": 15,
        "series_limit": 15,
        "slider_limit": 10,
        "primary_color": "#e50914",
        "font_family": "Inter",
        "footer_text": "© 2024 Drama Store. All Rights Reserved."
    })

# --- PREMIUM UI STYLES (Ultra Responsive) ---
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
    .btn-red { background: var(--p); color: white; border-radius: 8px; font-weight: bold; transition: 0.3s; }
    .btn-red:hover { transform: scale(1.05); background: #b20710; }
    .input-field { background: #0f172a; border: 1px solid #1e293b; color: white; padding: 12px; border-radius: 12px; width: 100%; outline: none; transition: 0.2s; }
    .input-field:focus { border-color: var(--p); box-shadow: 0 0 10px rgba(229, 9, 20, 0.2); }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .season-tab.active { border-bottom: 4px solid var(--p); color: var(--p); font-weight: 900; }
    .card-hover:hover { transform: translateY(-8px); transition: 0.4s; }
    .admin-sidebar a { display: flex; align-items: center; padding: 12px; border-radius: 10px; margin-bottom: 5px; transition: 0.2s; color: #94a3b8; }
    .admin-sidebar a:hover, .admin-sidebar a.active { background: #1e293b; color: white; }
</style>
"""

# --- UTILS ---
def get_conf(): return settings_col.find_one({"id": "config"})

# --- ROUTES ---

@app.route('/')
def index():
    conf = get_conf()
    search = request.args.get('s')
    query = {"title": {"$regex": search, "$options": "i"}} if search else {}
    
    # Separation of Data
    movies = list(contents_col.find({**query, "type": "movie"}).sort("_id", -1).limit(int(conf['movie_limit'])))
    series = list(contents_col.find({**query, "type": "tv"}).sort("_id", -1).limit(int(conf['series_limit'])))
    slider = list(contents_col.find().sort("views", -1).limit(int(conf['slider_limit'])))
    cats = list(cat_col.find())
    
    return render_template_string(HOME_HTML, ui=UI_HEAD, conf=conf, movies=movies, series=series, slider=slider, cats=cats)

@app.route('/view/<id>')
def view(id):
    item = contents_col.find_one({"_id": ObjectId(id)})
    contents_col.update_one({"_id": ObjectId(id)}, {"$inc": {"views": 1}})
    return render_template_string(DETAIL_HTML, ui=UI_HEAD, m=item, conf=get_conf())

# --- ADMIN SECTION ---

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        c = get_conf()
        if request.form.get('u') == c['admin_user'] and request.form.get('p') == c['admin_pass']:
            session['admin'] = True; return redirect('/admin/dashboard')
    return render_template_string(ADMIN_LOGIN_HTML, ui=UI_HEAD)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'): return redirect('/admin/login')
    stats = {
        "total": contents_col.count_documents({}),
        "movies": contents_col.count_documents({"type": "movie"}),
        "series": contents_col.count_documents({"type": "tv"}),
        "cats": cat_col.count_documents({})
    }
    return render_template_string(ADMIN_PANEL_HTML, ui=UI_HEAD, conf=get_conf(), stats=stats, cats=list(cat_col.find()))

@app.route('/admin/update_settings', methods=['POST'])
def update_settings():
    settings_col.update_one({"id": "config"}, {"$set": request.form.to_dict()})
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
        "logo": logo_url, "type": mtype, "views": 0, "movie_links": [], "seasons": [],
        "cats": request.form.getlist('cats')
    }
    contents_col.insert_one(content)
    return redirect('/admin/manage')

@app.route('/admin/manage')
def admin_manage():
    q = request.args.get('q', '')
    items = list(contents_col.find({"title": {"$regex": q, "$options": "i"}}).sort("_id", -1))
    return render_template_string(ADMIN_MANAGE_HTML, ui=UI_HEAD, items=items)

@app.route('/admin/add_ep', methods=['POST'])
def add_ep():
    id = request.form.get('id'); s = request.form.get('s'); e = request.form.get('e')
    links = []
    for row in request.form.get('links').split(','):
        p = row.split('|')
        if len(p) == 3: links.append({"q": p[0], "tg": p[1], "d": p[2]})
    
    contents_col.update_one({"_id": ObjectId(id), "seasons.sn": s}, {"$push": {"seasons.$.eps": {"en": e, "links": links}}}) or \
    contents_col.update_one({"_id": ObjectId(id)}, {"$push": {"seasons": {"sn": s, "eps": [{"en": e, "links": links}]}}})
    return redirect('/admin/manage')

@app.route('/admin/add_movie_link', methods=['POST'])
def add_movie_link():
    id = request.form.get('id')
    link = {"q": request.form.get('q'), "tg": request.form.get('tg'), "d": request.form.get('d')}
    contents_col.update_one({"_id": ObjectId(id)}, {"$push": {"movie_links": link}})
    return redirect('/admin/manage')

@app.route('/admin/cat_add', methods=['POST'])
def cat_add(): cat_col.insert_one({"name": request.form.get('name')}); return redirect('/admin/dashboard')

@app.route('/admin/delete/<id>')
def delete_item(id): contents_col.delete_one({"_id": ObjectId(id)}); return redirect('/admin/manage')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

# --- HTML TEMPLATES ---

HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <div class="flex items-center gap-4">
            <button onclick="document.getElementById('side').classList.toggle('hidden')" class="text-xl"><i class="fa fa-bars text-red-600"></i></button>
            <h1 class="text-2xl font-black text-red-600 italic tracking-tighter" onclick="location.href='/'">{{ conf.site_name }}</h1>
        </div>
        <form class="hidden md:flex bg-gray-900 border border-gray-800 rounded-full px-4 py-1 items-center">
            <input name="s" placeholder="Search Drama / Movie..." class="bg-transparent text-sm outline-none w-64">
            <button><i class="fa fa-search text-gray-500"></i></button>
        </form>
    </nav>

    <div id="side" class="hidden fixed inset-0 z-[60]">
        <div class="absolute inset-0 bg-black/90" onclick="this.parentElement.classList.add('hidden')"></div>
        <div class="absolute left-0 top-0 h-full w-80 glass p-10">
            <h2 class="text-3xl font-black text-red-600 mb-10 italic">DRAWER</h2>
            <div class="grid gap-6 font-bold">
                <a href="/"><i class="fa fa-home mr-3 text-red-600"></i> Home</a>
                <div class="text-[10px] text-gray-600 uppercase tracking-widest mt-4">Browse Categories</div>
                {% for c in cats %}<a href="/?s={{ c.name }}" class="text-sm hover:text-red-500">{{ c.name }}</a>{% endfor %}
                <hr class="border-gray-800">
                <a href="/admin/login" class="text-xs text-gray-500 italic">Login as Admin</a>
            </div>
        </div>
    </div>

    <div class="bg-red-600 text-white text-center py-1 font-black text-[10px] uppercase overflow-hidden"><marquee scrollamount="8">{{ conf.header_notice }}</marquee></div>

    <main class="p-4 md:px-16">
        <div class="flex gap-4 overflow-x-auto no-scrollbar py-6">
            {% for m in slider %}
            <div class="min-w-[320px] md:min-w-[500px] h-48 md:h-72 relative rounded-[30px] overflow-hidden flex-shrink-0 cursor-pointer" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover">
                <div class="absolute inset-0 bg-gradient-to-t from-black via-transparent p-8 flex flex-col justify-end">
                    <p class="text-2xl font-black tracking-tighter uppercase">{{ m.title }}</p>
                    <span class="text-xs text-gray-400 font-bold uppercase tracking-widest">{{ m.year }} • {{ m.lang }}</span>
                </div>
            </div>
            {% endfor %}
        </div>

        <h2 class="text-2xl font-black mb-8 mt-12 border-l-8 border-red-600 pl-4 italic tracking-tighter uppercase">Latest Dramas & Series</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
            {% for m in series %}
            <div class="card-hover cursor-pointer" onclick="location.href='/view/{{ m._id }}'">
                <div class="relative rounded-2xl overflow-hidden aspect-[2/3] border border-gray-800 shadow-2xl">
                    <img src="{{ m.poster }}" class="w-full h-full object-cover">
                    <div class="absolute top-2 right-2 bg-red-600 text-[10px] px-2 py-1 font-black rounded-lg">EPISODIC</div>
                </div>
                <div class="mt-3"><h3 class="font-bold text-sm truncate uppercase">{{ m.title }}</h3><p class="text-[10px] text-gray-500">{{ m.year }}</p></div>
            </div>
            {% endfor %}
        </div>

        <h2 class="text-2xl font-black mb-8 mt-12 border-l-8 border-red-600 pl-4 italic tracking-tighter uppercase">Exclusive Movies</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
            {% for m in movies %}
            <div class="card-hover cursor-pointer" onclick="location.href='/view/{{ m._id }}'">
                <div class="relative rounded-2xl overflow-hidden aspect-[2/3] border border-gray-800 shadow-2xl">
                    <img src="{{ m.poster }}" class="w-full h-full object-cover">
                </div>
                <div class="mt-3"><h3 class="font-bold text-sm truncate uppercase">{{ m.title }}</h3><p class="text-[10px] text-gray-500">{{ m.year }}</p></div>
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
        <div class="absolute inset-0 bg-gradient-to-t from-[#05070a] via-transparent"></div>
        <button onclick="history.back()" class="absolute top-8 left-8 glass h-12 w-12 rounded-full flex items-center justify-center"><i class="fa fa-arrow-left"></i></button>
        <div class="absolute bottom-12 left-6 md:left-20">
            {% if m.logo %}<img src="{{ m.logo }}" class="w-64 md:w-[400px] mb-6">
            {% else %}<h1 class="text-5xl md:text-8xl font-black italic tracking-tighter uppercase mb-4">{{ m.title }}</h1>{% endif %}
            <div class="flex gap-4 text-xs font-black text-gray-400 items-center uppercase tracking-widest">
                <span class="bg-red-600 text-white px-2 py-1 rounded">ULTRA HD</span>
                <span>{{ m.year }}</span>
                <span>{{ m.lang }}</span>
                <span><i class="fa fa-eye"></i> {{ m.views }}</span>
            </div>
        </div>
    </div>

    <div class="p-6 md:p-20">
        <p class="text-gray-400 max-w-4xl text-sm md:text-lg mb-12 leading-relaxed font-semibold italic">{{ m.story }}</p>

        {% if m.type == 'movie' %}
            <h3 class="text-2xl font-black mb-8 italic border-l-4 border-red-600 pl-4">DOWNLOAD LINKS</h3>
            <div class="grid gap-4 max-w-3xl">
                {% for l in m.movie_links %}
                <div class="glass p-5 rounded-3xl flex justify-between items-center hover:border-red-600 transition">
                    <div class="font-black text-red-600 italic uppercase tracking-widest">{{ l.q }}</div>
                    <div class="flex gap-4">
                        <a href="{{ l.tg }}" class="text-sky-500"><i class="fab fa-telegram text-2xl"></i></a>
                        <a href="{{ l.d }}" class="bg-white text-black px-6 py-2 rounded-2xl font-black text-[10px] italic">GET DOWNLOAD</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <div class="flex gap-6 border-b border-gray-900 mb-10 overflow-x-auto no-scrollbar">
                {% for s in m.seasons %}
                <button onclick="tab('{{ s.sn }}')" class="season-tab px-6 py-4 uppercase font-black italic tracking-tighter" id="btn-{{ s.sn }}">Season {{ s.sn }}</button>
                {% endfor %}
            </div>
            {% for s in m.seasons %}
            <div class="s-box hidden grid gap-6" id="box-{{ s.sn }}">
                {% for ep in s.eps %}
                <div class="glass p-8 rounded-[40px]">
                    <p class="text-gray-500 font-black text-[10px] uppercase mb-4 tracking-widest italic">Episode {{ ep.en }}</p>
                    <div class="grid md:grid-cols-2 gap-4">
                        {% for l in ep.links %}
                        <div class="bg-gray-800/30 p-4 rounded-2xl flex justify-between items-center border border-white/5">
                            <span class="text-red-600 font-black italic text-xs uppercase">{{ l.q }}</span>
                            <div class="flex gap-4">
                                <a href="{{ l.tg }}" class="text-sky-500"><i class="fab fa-telegram"></i></a>
                                <a href="{{ l.d }}" class="bg-white text-black px-4 py-1.5 rounded-full text-[8px] font-black italic uppercase">Download</a>
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
        function tab(n){
            document.querySelectorAll('.s-box').forEach(b => b.classList.add('hidden'));
            document.querySelectorAll('.season-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('box-'+n).classList.remove('hidden');
            document.getElementById('btn-'+n).classList.add('active');
        }
        window.onload = () => { if(document.querySelector('.season-tab')) document.querySelector('.season-tab').click(); }
    </script>
</body>
</html>
"""

ADMIN_PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Mega Control</title></head>
<body class="flex flex-col md:flex-row min-h-screen">
    <!-- MEGA SIDEBAR -->
    <div class="w-full md:w-80 h-screen glass p-8 sticky top-0 admin-sidebar overflow-y-auto">
        <h2 class="text-red-600 font-black text-3xl italic mb-10 tracking-tighter">ADMIN BOX</h2>
        <a href="#dash" class="active"><i class="fa fa-th-large mr-3"></i> Dashboard</a>
        <a href="#identity"><i class="fa fa-id-card mr-3"></i> Name & Logo</a>
        <a href="#notice"><i class="fa fa-bullhorn mr-3"></i> Header Notice</a>
        <a href="#limits"><i class="fa fa-sliders mr-3"></i> Site Limits</a>
        <a href="#cats"><i class="fa fa-tags mr-3"></i> Category Manager</a>
        <a href="/admin/manage"><i class="fa fa-tasks mr-3"></i> Content & Links</a>
        <a href="/logout" class="mt-20 text-red-900"><i class="fa fa-sign-out mr-3"></i> Logout</a>
    </div>

    <div class="flex-1 p-6 md:p-12 space-y-10">
        <div id="dash" class="grid md:grid-cols-4 gap-6">
            <div class="glass p-6 rounded-3xl text-center"><p class="text-[10px] text-gray-500 uppercase font-black">Total Items</p><h3 class="text-4xl font-black text-red-600">{{ stats.total }}</h3></div>
            <div class="glass p-6 rounded-3xl text-center"><p class="text-[10px] text-gray-500 uppercase font-black">Movies</p><h3 class="text-4xl font-black text-white">{{ stats.movies }}</h3></div>
            <div class="glass p-6 rounded-3xl text-center"><p class="text-[10px] text-gray-500 uppercase font-black">Series</p><h3 class="text-4xl font-black text-white">{{ stats.series }}</h3></div>
            <div class="glass p-6 rounded-3xl text-center"><p class="text-[10px] text-gray-500 uppercase font-black">Categories</p><h3 class="text-4xl font-black text-white">{{ stats.cats }}</h3></div>
        </div>

        <div id="identity" class="glass p-10 rounded-[40px]">
            <h3 class="font-black mb-6 italic tracking-tighter text-red-600 uppercase">Site Identity</h3>
            <form action="/admin/update_settings" method="POST" class="grid md:grid-cols-2 gap-6">
                <input name="site_name" value="{{ conf.site_name }}" class="input-field" placeholder="Website Name">
                <input name="site_logo" value="{{ conf.site_logo }}" class="input-field" placeholder="Logo PNG URL">
                <button class="btn-red py-3 md:col-span-2">Update Identity</button>
            </form>
        </div>

        <div id="notice" class="glass p-10 rounded-[40px]">
            <h3 class="font-black mb-6 italic tracking-tighter text-red-600 uppercase">Header Notice</h3>
            <form action="/admin/update_settings" method="POST" class="grid gap-6">
                <textarea name="header_notice" class="input-field h-24">{{ conf.header_notice }}</textarea>
                <button class="btn-red py-3">Publish Notice</button>
            </form>
        </div>

        <div id="limits" class="glass p-10 rounded-[40px]">
            <h3 class="font-black mb-6 italic tracking-tighter text-red-600 uppercase">Site Limits (Home)</h3>
            <form action="/admin/update_settings" method="POST" class="grid md:grid-cols-3 gap-6">
                <input name="movie_limit" value="{{ conf.movie_limit }}" class="input-field" placeholder="Movie Count">
                <input name="series_limit" value="{{ conf.series_limit }}" class="input-field" placeholder="Series Count">
                <input name="slider_limit" value="{{ conf.slider_limit }}" class="input-field" placeholder="Slider Count">
                <button class="btn-red py-3 md:col-span-3">Apply Limits</button>
            </form>
        </div>

        <div id="cats" class="glass p-10 rounded-[40px]">
            <h3 class="font-black mb-6 italic tracking-tighter text-red-600 uppercase">Category Manager</h3>
            <form action="/admin/cat_add" method="POST" class="flex gap-4 mb-6">
                <input name="name" class="input-field" placeholder="New Category Name">
                <button class="btn-red px-10">ADD</button>
            </form>
            <div class="flex flex-wrap gap-2">
                {% for c in cats %}<span class="bg-gray-800 px-4 py-2 rounded-xl text-xs font-bold">{{ c.name }}</span>{% endfor %}
            </div>
        </div>

        <div class="glass p-10 rounded-[40px] border-red-600/30">
            <h3 class="font-black mb-6 italic tracking-tighter text-red-600 uppercase">Upload Content (TMDB Auto)</h3>
            <form action="/admin/add_auto" method="POST" class="grid md:grid-cols-3 gap-4">
                <select name="type" class="input-field"><option value="movie">Movie</option><option value="tv">TV Series</option></select>
                <input name="tid" class="input-field col-span-2" placeholder="Enter TMDB ID">
                <div class="col-span-3 p-4 bg-black/40 rounded-2xl grid grid-cols-2 md:grid-cols-4 gap-4">
                    {% for c in cats %}<label class="text-xs"><input type="checkbox" name="cats" value="{{ c.name }}"> {{ c.name }}</label>{% endfor %}
                </div>
                <button class="btn-red py-4 col-span-3 text-xl font-black italic tracking-widest">FETCH & SAVE CONTENT</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

ADMIN_MANAGE_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Manage All</title></head>
<body class="p-10">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-12">
            <h2 class="text-4xl font-black italic tracking-tighter uppercase"><i class="fa fa-tasks text-red-600 mr-4"></i> Management</h2>
            <a href="/admin/dashboard" class="text-red-500 font-bold uppercase text-xs tracking-widest">Back to Hub</a>
        </div>

        <form class="flex gap-4 mb-12">
            <input name="q" class="input-field flex-1" placeholder="Search by name to edit or add links...">
            <button class="btn-red px-10">SEARCH</button>
        </form>

        <div class="space-y-8">
            {% for m in items %}
            <div class="glass p-8 rounded-[40px] flex flex-col md:flex-row items-center gap-8">
                <img src="{{ m.poster }}" class="h-32 w-24 rounded-2xl object-cover border border-gray-800 shadow-2xl">
                <div class="flex-1 text-center md:text-left">
                    <h4 class="text-2xl font-black italic uppercase tracking-tighter">{{ m.title }}</h4>
                    <p class="text-[10px] text-gray-500 font-black uppercase mt-1">{{ m.type }} | {{ m.year }} | {{ m.views }} Views</p>
                </div>
                
                <div class="w-full md:w-[400px]">
                    {% if m.type == 'tv' %}
                    <form action="/admin/add_ep" method="POST" class="grid grid-cols-2 md:grid-cols-4 gap-2">
                        <input type="hidden" name="id" value="{{ m._id }}">
                        <input name="s" placeholder="S-No" class="input-field text-[10px] p-2">
                        <input name="e" placeholder="E-No" class="input-field text-[10px] p-2">
                        <input name="links" placeholder="Q|TG|D" class="input-field text-[10px] p-2">
                        <button class="bg-indigo-600 text-[8px] font-black uppercase rounded-lg">Add EP</button>
                    </form>
                    {% else %}
                    <form action="/admin/add_movie_link" method="POST" class="grid grid-cols-4 gap-2">
                        <input type="hidden" name="id" value="{{ m._id }}">
                        <input name="q" placeholder="Q" class="input-field text-[10px] p-2">
                        <input name="tg" placeholder="TG" class="input-field text-[10px] p-2">
                        <input name="d" placeholder="D" class="input-field text-[10px] p-2">
                        <button class="bg-blue-600 text-[8px] font-black uppercase rounded-lg">Add Link</button>
                    </form>
                    {% endif %}
                </div>
                <a href="/admin/delete/{{ m._id }}" class="text-red-900 font-black text-xs uppercase" onclick="return confirm('Kill this item?')">Delete</a>
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
<body class="flex items-center justify-center min-h-screen p-10">
    <div class="glass p-16 rounded-[60px] w-full max-w-lg shadow-2xl border-white/5 text-center">
        <h2 class="text-5xl font-black text-red-600 italic tracking-tighter mb-10">ADMIN HUB</h2>
        <form method="POST" class="grid gap-6">
            <input name="u" placeholder="Admin Username" class="input-field text-center text-lg" required>
            <input name="p" type="password" placeholder="Gate Passcode" class="input-field text-center text-lg" required>
            <button class="w-full btn-red py-5 rounded-3xl font-black text-xl italic tracking-widest shadow-2xl shadow-red-900/30">UNSEAL ACCESS</button>
        </form>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
