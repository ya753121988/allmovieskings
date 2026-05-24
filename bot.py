import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "ULTIMATE_DRAMA_STORE_FIXED_FINAL_V3"

# --- ডাটাবেজ এবং API কনফিগারেশন ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['DramaStoreB']
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

# --- UI CSS (রেসপনসিভ মেনু ও ডিজাইন) ---
UI_HEAD = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;900&display=swap');
    :root { --p: #e50914; --bg: #05070a; }
    body { background: var(--bg); color: #f8fafc; font-family: 'Inter', sans-serif; margin: 0; }
    .glass { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(15px); border: 1px solid rgba(255,255,255,0.05); }
    .btn-red { background: var(--p); color: white; border-radius: 8px; font-weight: bold; transition: 0.3s; padding: 10px 20px; text-align: center; cursor: pointer; display: inline-block; }
    .btn-red:hover { background: #b20710; transform: scale(1.02); }
    .input-field { background: #0f172a; border: 1px solid #1e293b; color: white; padding: 12px; border-radius: 12px; width: 100%; outline: none; }
    .input-field:focus { border-color: var(--p); }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .tab-active { border-bottom: 4px solid var(--p); color: var(--p); font-weight: 900; }
    
    /* Sidebar Design */
    #adminSidebar { position: fixed; top: 0; left: -100%; height: 100%; width: 280px; z-index: 2000; transition: 0.4s; background: #0f172a; border-right: 1px solid #1e293b; overflow-y: auto; }
    #adminSidebar.active { left: 0; }
    @media (min-width: 1024px) {
        #adminSidebar { position: sticky; left: 0; width: 320px; }
        .menu-toggle { display: none; }
    }
    .nav-link { display: flex; align-items: center; padding: 14px; border-radius: 12px; color: #94a3b8; margin-bottom: 5px; transition: 0.3s; }
    .nav-link:hover, .nav-link.active { background: var(--p); color: white; }
</style>
"""

# -----------------------------------------------------------
# ROUTES
# -----------------------------------------------------------

@app.route('/')
def index():
    conf = settings_col.find_one({"id": "config"})
    search = request.args.get('s', '')
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

# --- ADMIN AUTH ---
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        c = settings_col.find_one({"id": "config"})
        if request.form.get('u') == c['admin_user'] and request.form.get('p') == c['admin_pass']:
            session['admin'] = True; return redirect('/admin/dashboard')
    return render_template_string(ADMIN_LOGIN_HTML, ui=UI_HEAD)

# --- ADMIN DASHBOARD & CONTENT SAVE ---
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'): return redirect('/admin/login')
    conf = settings_col.find_one({"id": "config"})
    cats = list(cat_col.find())
    stats = {"total": contents_col.count_documents({}), "movie": contents_col.count_documents({"type":"movie"}), "tv": contents_col.count_documents({"type":"tv"})}
    edit_item = None
    eid = request.args.get('edit')
    if eid: edit_item = contents_col.find_one({"_id": ObjectId(eid)})
    return render_template_string(ADMIN_DASHBOARD_HTML, ui=UI_HEAD, conf=conf, cats=cats, stats=stats, edit=edit_item)

@app.route('/admin/save', methods=['POST'])
def admin_save():
    if not session.get('admin'): return redirect('/admin/login')
    cid = request.form.get('cid')
    data = {
        "title": request.form.get('title'), "lang": request.form.get('lang'),
        "year": request.form.get('year'), "story": request.form.get('story'),
        "poster": request.form.get('poster'), "backdrop": request.form.get('backdrop'),
        "logo": request.form.get('logo'), "type": request.form.get('type'),
        "category": request.form.getlist('cats'),
        "images": request.form.get('images', '').split(',')
    }
    if cid:
        contents_col.update_one({"_id": ObjectId(cid)}, {"$set": data})
    else:
        data["views"] = 0; data["movie_links"] = []; data["seasons"] = []
        contents_col.insert_one(data)
    return redirect('/admin/manage')

# --- MANAGE & BULK DELETE ---
@app.route('/admin/manage')
def admin_manage():
    if not session.get('admin'): return redirect('/admin/login')
    q = request.args.get('q', '')
    items = list(contents_col.find({"title": {"$regex": q, "$options": "i"}}).sort("_id", -1))
    return render_template_string(ADMIN_MANAGE_HTML, ui=UI_HEAD, items=items, q=q)

@app.route('/admin/bulk_delete', methods=['POST'])
def bulk_delete():
    if not session.get('admin'): return redirect('/admin/login')
    ids = request.form.getlist('selected_ids')
    if ids:
        contents_col.delete_many({"_id": {"$in": [ObjectId(i) for i in ids]}})
    return redirect('/admin/manage')

@app.route('/admin/delete/<id>')
def admin_delete(id):
    if not session.get('admin'): return redirect('/admin/login')
    contents_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/manage')

# --- CATEGORY MANAGEMENT ---
@app.route('/admin/categories', methods=['GET', 'POST'])
def admin_categories():
    if not session.get('admin'): return redirect('/admin/login')
    if request.method == 'POST':
        cat_col.insert_one({"name": request.form.get('name')})
    cats = list(cat_col.find())
    return render_template_string(ADMIN_CAT_HTML, ui=UI_HEAD, cats=cats)

@app.route('/admin/cat/delete/<id>')
def cat_delete(id):
    if not session.get('admin'): return redirect('/admin/login')
    cat_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/categories')

# --- SERIES & LINKS MANAGEMENT ---
@app.route('/admin/links/<id>', methods=['GET', 'POST'])
def manage_links(id):
    if not session.get('admin'): return redirect('/admin/login')
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

@app.route('/admin/series/<id>', methods=['GET', 'POST'])
def manage_series(id):
    if not session.get('admin'): return redirect('/admin/login')
    if request.method == 'POST':
        action = request.form.get('action')
        sn = request.form.get('sn')
        if action == 'add_ep':
            qualities = request.form.getlist('q[]')
            tg_links = request.form.getlist('tg[]')
            d_links = request.form.getlist('d[]')
            
            links_list = []
            for i in range(len(qualities)):
                if qualities[i]:
                    links_list.append({"q": qualities[i], "tg": tg_links[i], "d": d_links[i]})

            ep = {
                "id": str(ObjectId()), 
                "en": request.form.get('en'),
                "links": links_list
            }
            res = contents_col.update_one({"_id": ObjectId(id), "seasons.sn": sn}, {"$push": {"seasons.$.eps": ep}})
            if res.matched_count == 0:
                contents_col.update_one({"_id": ObjectId(id)}, {"$push": {"seasons": {"sn": sn, "eps": [ep]}}})
        elif action == 'del_ep':
            eid = request.form.get('eid')
            contents_col.update_one({"_id": ObjectId(id), "seasons.sn": sn}, {"$pull": {"seasons.$.eps": {"id": eid}}})
        elif action == 'del_season':
            contents_col.update_one({"_id": ObjectId(id)}, {"$pull": {"seasons": {"sn": sn}}})
    item = contents_col.find_one({"_id": ObjectId(id)})
    return render_template_string(ADMIN_SERIES_HTML, ui=UI_HEAD, m=item)

# --- SETTINGS & NOTICE ---
@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not session.get('admin'): return redirect('/admin/login')
    if request.method == 'POST':
        settings_col.update_one({"id": "config"}, {"$set": request.form.to_dict()})
        return redirect('/admin/settings')
    conf = settings_col.find_one({"id": "config"})
    return render_template_string(ADMIN_SETTINGS_HTML, ui=UI_HEAD, conf=conf)

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

# --- TMDB HELPER ---
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
    backdrops = res.get('images', {}).get('backdrops', [])
    posters = res.get('images', {}).get('posters', [])
    
    gallery = []
    for b in backdrops[:10]: gallery.append(f"https://image.tmdb.org/t/p/original{b['file_path']}")
    for p in posters[:10]: gallery.append(f"https://image.tmdb.org/t/p/original{p['file_path']}")
    
    logo = f"https://image.tmdb.org/t/p/original{logos[0]['file_path']}" if logos else ""
    return jsonify({"data": res, "logo": logo, "gallery": ",".join(gallery)})

# --------------------------------------------------------------------------------------
# HTML TEMPLATES
# --------------------------------------------------------------------------------------

SIDEBAR_HTML = """
<div id="adminSidebar" class="p-6">
    <div class="flex justify-between items-center mb-10">
        <h2 class="text-red-600 font-black text-2xl italic tracking-tighter">ADMIN BOX</h2>
        <button class="lg:hidden text-2xl" onclick="toggleSidebar()"><i class="fa fa-times text-white"></i></button>
    </div>
    <nav>
        <a href="/admin/dashboard" class="nav-link"><i class="fa fa-plus-circle w-8"></i> Add Content</a>
        <a href="/admin/manage" class="nav-link"><i class="fa fa-film w-8"></i> Manage Movies</a>
        <a href="/admin/categories" class="nav-link"><i class="fa fa-list w-8"></i> Categories</a>
        <a href="/admin/settings" class="nav-link"><i class="fa fa-cog w-8"></i> Site Settings</a>
        <div class="mt-10 border-t border-gray-800 pt-5">
            <a href="/" target="_blank" class="nav-link text-blue-400"><i class="fa fa-external-link w-8"></i> View Site</a>
            <a href="/logout" class="nav-link text-red-500"><i class="fa fa-sign-out w-8"></i> Logout</a>
        </div>
    </nav>
</div>
<script>function toggleSidebar(){ document.getElementById('adminSidebar').classList.toggle('active'); }</script>
"""

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Add/Edit Content</title></head>
<body class="flex flex-col lg:flex-row min-h-screen">
    <div class="lg:hidden p-4 glass sticky top-0 z-[1500] flex justify-between items-center">
        <h2 class="text-red-600 font-black italic">ADMIN PANEL</h2>
        <button onclick="toggleSidebar()" class="text-2xl"><i class="fa fa-bars"></i></button>
    </div>
    """ + SIDEBAR_HTML + """
    <div class="flex-1 p-4 md:p-10 space-y-8">
        <div class="glass p-6 md:p-8 rounded-[40px] border-red-600/10">
            <h3 class="text-xl font-black mb-6 text-red-600 italic uppercase">Auto Fetch (TMDB)</h3>
            <div class="flex flex-col sm:flex-row gap-4">
                <select id="tmdb_type" class="input-field sm:w-32"><option value="movie">Movie</option><option value="tv">TV Series</option></select>
                <input id="tmdb_q" placeholder="Enter Name..." class="input-field">
                <button onclick="searchTMDB()" class="btn-red">SEARCH</button>
            </div>
            <div id="results" class="flex gap-4 overflow-x-auto no-scrollbar py-6"></div>
        </div>

        <form action="/admin/save" method="POST" class="glass p-6 md:p-8 rounded-[40px] grid grid-cols-1 lg:grid-cols-2 gap-8">
            <input type="hidden" name="cid" value="{{ edit._id if edit else '' }}">
            <input type="hidden" name="type" id="f_type" value="{{ edit.type if edit else 'movie' }}">
            <input type="hidden" name="images" id="f_gallery" value="{{ ','.join(edit.images) if edit and edit.images else '' }}">
            <div>
                <label class="text-[10px] uppercase font-bold text-gray-500 ml-2">Title</label>
                <input name="title" id="f_title" value="{{ edit.title if edit else '' }}" class="input-field mb-4" required>
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <input name="year" id="f_year" value="{{ edit.year if edit else '' }}" placeholder="Year" class="input-field">
                    <input name="lang" id="f_lang" value="{{ edit.lang if edit else '' }}" placeholder="Language" class="input-field">
                </div>
                <input name="poster" id="f_poster" value="{{ edit.poster if edit else '' }}" placeholder="Poster URL" class="input-field mb-2">
                <input name="backdrop" id="f_backdrop" value="{{ edit.backdrop if edit else '' }}" placeholder="Backdrop URL" class="input-field mb-2">
                <input name="logo" id="f_logo" value="{{ edit.logo if edit else '' }}" placeholder="Logo URL" class="input-field">
            </div>
            <div>
                <label class="text-[10px] uppercase font-bold text-gray-500 ml-2">Categories</label>
                <div class="grid grid-cols-2 gap-2 bg-black/40 p-4 rounded-2xl h-32 overflow-y-auto mb-4 border border-gray-800">
                    {% for c in cats %}<label class="text-xs"><input type="checkbox" name="cats" value="{{ c.name }}" {{ 'checked' if edit and c.name in edit.category else '' }}> {{ c.name }}</label>{% endfor %}
                </div>
                <textarea name="story" id="f_story" placeholder="Storyline..." class="input-field h-32">{{ edit.story if edit else '' }}</textarea>
                <button class="w-full btn-red py-4 mt-6 uppercase font-black text-lg italic">{{ 'Update' if edit else 'Save' }} Content</button>
            </div>
        </form>
    </div>
    <script>
        async function searchTMDB(){
            const q = document.getElementById('tmdb_q').value;
            const t = document.getElementById('tmdb_type').value;
            const res = await fetch(`/api/tmdb_search?q=${q}&t=${t}`);
            const data = await res.json();
            const div = document.getElementById('results'); div.innerHTML = '';
            data.results.forEach(m => {
                div.innerHTML += `<div class="min-w-[120px] cursor-pointer" onclick="fill('${m.id}', '${t}')"><img src="https://image.tmdb.org/t/p/w200${m.poster_path}" class="rounded-xl border-2 border-transparent hover:border-red-600 transition"></div>`;
            });
        }
        async function fill(id, type){
            const res = await fetch(`/api/tmdb_info?id=${id}&t=${type}`);
            const j = await res.json(); const d = j.data;
            document.getElementById('f_title').value = d.title || d.name;
            document.getElementById('f_year').value = (d.release_date || d.first_air_date || '').split('-')[0];
            document.getElementById('f_lang').value = (d.original_language || '').toUpperCase();
            document.getElementById('f_poster').value = 'https://image.tmdb.org/t/p/w500' + d.poster_path;
            document.getElementById('f_backdrop').value = 'https://image.tmdb.org/t/p/original' + d.backdrop_path;
            document.getElementById('f_logo').value = j.logo;
            document.getElementById('f_gallery').value = j.gallery;
            document.getElementById('f_story').value = d.overview;
            document.getElementById('f_type').value = type;
            alert("Data Loaded!");
        }
    </script>
</body>
</html>
"""

ADMIN_MANAGE_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Manage Content</title></head>
<body class="flex flex-col lg:flex-row min-h-screen">
    <div class="lg:hidden p-4 glass sticky top-0 z-[1500] flex justify-between items-center">
        <h2 class="text-red-600 font-black italic uppercase">Manage</h2>
        <button onclick="toggleSidebar()" class="text-2xl"><i class="fa fa-bars"></i></button>
    </div>
    """ + SIDEBAR_HTML + """
    <div class="flex-1 p-4 md:p-10">
        <div class="flex flex-col md:flex-row justify-between items-center gap-4 mb-8">
            <h2 class="text-2xl font-black italic uppercase">Manage Content</h2>
            <form class="flex w-full md:w-auto bg-gray-900 rounded-full px-4 border border-gray-800">
                <input name="q" value="{{ q }}" placeholder="Search here..." class="bg-transparent p-2 outline-none w-full md:w-64">
                <button><i class="fa fa-search"></i></button>
            </form>
        </div>
        <form action="/admin/bulk_delete" method="POST">
            <div class="flex gap-4 mb-6">
                <label class="flex items-center gap-2 cursor-pointer bg-gray-800 px-4 py-2 rounded-xl text-xs">
                    <input type="checkbox" id="selectAll" onclick="toggleSelectAll(this)"> Select All
                </label>
                <button type="submit" class="bg-red-900 px-6 py-2 rounded-xl text-xs font-bold uppercase" onclick="return confirm('Delete selected?')">Bulk Kill</button>
            </div>
            <div class="grid gap-4">
                {% for m in items %}
                <div class="glass p-4 rounded-3xl flex items-center justify-between gap-4">
                    <div class="flex items-center gap-4">
                        <input type="checkbox" name="selected_ids" value="{{ m._id }}" class="item-checkbox">
                        <img src="{{ m.poster }}" class="h-16 w-12 rounded-lg object-cover">
                        <div class="truncate">
                            <h4 class="font-bold text-sm md:text-lg truncate">{{ m.title }}</h4>
                            <span class="text-[10px] uppercase text-gray-500">{{ m.type }} | {{ m.year }}</span>
                        </div>
                    </div>
                    <div class="flex gap-2">
                        <a href="/admin/dashboard?edit={{ m._id }}" class="bg-blue-600 p-2 rounded-lg text-xs"><i class="fa fa-edit"></i></a>
                        {% if m.type == 'movie' %}
                        <a href="/admin/links/{{ m._id }}" class="bg-indigo-600 p-2 rounded-lg text-xs"><i class="fa fa-link"></i></a>
                        {% else %}
                        <a href="/admin/series/{{ m._id }}" class="bg-indigo-600 p-2 rounded-lg text-xs"><i class="fa fa-list-ol"></i></a>
                        {% endif %}
                        <a href="/admin/delete/{{ m._id }}" class="bg-red-800 p-2 rounded-lg text-xs" onclick="return confirm('Delete?')"><i class="fa fa-trash"></i></a>
                    </div>
                </div>
                {% endfor %}
            </div>
        </form>
    </div>
    <script>function toggleSelectAll(source) { checkboxes = document.getElementsByClassName('item-checkbox'); for(var i in checkboxes) checkboxes[i].checked = source.checked; }</script>
</body>
</html>
"""

ADMIN_CAT_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Categories</title></head>
<body class="flex flex-col lg:flex-row min-h-screen">
    <div class="lg:hidden p-4 glass sticky top-0 z-[1500] flex justify-between items-center">
        <h2 class="text-red-600 font-black">CATEGORIES</h2>
        <button onclick="toggleSidebar()"><i class="fa fa-bars"></i></button>
    </div>
    """ + SIDEBAR_HTML + """
    <div class="flex-1 p-6 md:p-12 max-w-4xl">
        <h2 class="text-2xl font-black italic mb-10">CATEGORY MANAGER</h2>
        <form method="POST" class="flex gap-4 mb-10">
            <input name="name" placeholder="New Category Name" class="input-field" required>
            <button class="btn-red">Add</button>
        </form>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
            {% for c in cats %}
            <div class="glass p-4 rounded-2xl flex justify-between items-center">
                <span class="font-bold">{{ c.name }}</span>
                <a href="/admin/cat/delete/{{ c._id }}" class="text-red-600 p-2"><i class="fa fa-trash"></i></a>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

ADMIN_SETTINGS_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Settings</title></head>
<body class="flex flex-col lg:flex-row min-h-screen">
    <div class="lg:hidden p-4 glass sticky top-0 z-[1500] flex justify-between items-center">
        <h2 class="text-red-600 font-black italic">SETTINGS</h2>
        <button onclick="toggleSidebar()"><i class="fa fa-bars"></i></button>
    </div>
    """ + SIDEBAR_HTML + """
    <div class="flex-1 p-6 md:p-12 max-w-4xl">
        <h2 class="text-2xl font-black italic mb-10">SITE CONFIGURATION</h2>
        <form method="POST" class="glass p-8 rounded-[40px] space-y-6">
            <div><label class="text-xs uppercase text-gray-500 font-bold block mb-2">Site Name</label><input name="site_name" value="{{ conf.site_name }}" class="input-field"></div>
            <div><label class="text-xs uppercase text-gray-500 font-bold block mb-2">Site Logo URL</label><input name="site_logo" value="{{ conf.site_logo }}" class="input-field"></div>
            <div><label class="text-xs uppercase text-gray-500 font-bold block mb-2">Header Notice</label><textarea name="header_notice" class="input-field h-24">{{ conf.header_notice }}</textarea></div>
            <div class="grid grid-cols-2 gap-4">
                <div><label class="text-xs text-gray-500">Admin User</label><input name="admin_user" value="{{ conf.admin_user }}" class="input-field"></div>
                <div><label class="text-xs text-gray-500">Admin Pass</label><input name="admin_pass" value="{{ conf.admin_pass }}" class="input-field"></div>
            </div>
            <button class="w-full btn-red py-4 uppercase font-black italic">Save All Settings</button>
        </form>
    </div>
</body>
</html>
"""

ADMIN_LINKS_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Movie Links</title></head>
<body class="p-4 md:p-10">
    <div class="max-w-4xl mx-auto glass p-6 md:p-10 rounded-[50px]">
        <h2 class="text-xl md:text-3xl font-black mb-8 italic uppercase">Links: {{ m.title }}</h2>
        <form method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
            <input type="hidden" name="action" value="add">
            <input name="q" placeholder="Quality" class="input-field" required>
            <input name="tg" placeholder="TG Link" class="input-field" required>
            <input name="d" placeholder="Direct Link" class="input-field" required>
            <button class="btn-red">Add</button>
        </form>
        <div class="space-y-3">
            {% for l in m.movie_links %}
            <div class="bg-black/40 p-4 rounded-xl flex justify-between items-center">
                <span class="font-black text-red-600 uppercase">{{ l.q }}</span>
                <form method="POST"><input type="hidden" name="action" value="delete"><input type="hidden" name="lid" value="{{ l.id }}"><button class="text-red-900"><i class="fa fa-trash"></i></button></form>
            </div>
            {% endfor %}
        </div>
        <a href="/admin/manage" class="block mt-10 text-center text-xs text-gray-500 italic">Back to Hub</a>
    </div>
</body>
</html>
"""

ADMIN_SERIES_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Series Manager</title></head>
<body class="p-4 md:p-10">
    <div class="max-w-5xl mx-auto glass p-6 md:p-10 rounded-[50px]">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-xl md:text-3xl font-black italic uppercase">Manage Series: {{ m.title }}</h2>
            <a href="/admin/manage" class="btn-red text-xs">Back</a>
        </div>

        <form method="POST" class="bg-white/5 p-6 rounded-3xl mb-12">
            <input type="hidden" name="action" value="add_ep">
            <div class="grid grid-cols-2 gap-4 mb-6">
                <input name="sn" placeholder="Season No (e.g. 1)" class="input-field" required>
                <input name="en" placeholder="Episode No" class="input-field" required>
            </div>
            
            <div id="quality_inputs" class="space-y-4">
                <div class="grid grid-cols-3 gap-2 bg-black/20 p-4 rounded-xl border border-gray-800">
                    <input name="q[]" placeholder="Quality (e.g. 720p)" class="input-field text-xs">
                    <input name="tg[]" placeholder="Telegram Link" class="input-field text-xs">
                    <input name="d[]" placeholder="Direct Download Link" class="input-field text-xs">
                </div>
            </div>
            
            <button type="button" onclick="addMoreQuality()" class="mt-4 text-xs text-blue-400 font-bold uppercase">+ Add More Quality</button>
            <button class="w-full btn-red mt-8 uppercase font-black">Save Episode</button>
        </form>

        {% for s in m.seasons %}
        <div class="mb-10 bg-black/30 p-6 rounded-[30px] border border-gray-900">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-xl font-black text-red-600 italic">Season {{ s.sn }}</h3>
                <form method="POST"><input type="hidden" name="action" value="del_season"><input type="hidden" name="sn" value="{{ s.sn }}"><button class="text-red-900 text-xs font-bold uppercase">Delete Season</button></form>
            </div>
            <div class="grid gap-4">
                {% for ep in s.eps %}
                <div class="glass p-4 rounded-2xl flex justify-between items-center">
                    <div class="font-black text-xs uppercase">Episode {{ ep.en }} ({{ ep.links|length }} Links)</div>
                    <form method="POST"><input type="hidden" name="action" value="del_ep"><input type="hidden" name="sn" value="{{ s.sn }}"><input type="hidden" name="eid" value="{{ ep.id }}"><button class="text-red-900"><i class="fa fa-trash"></i></button></form>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
    <script>
        function addMoreQuality(){
            const div = document.createElement('div');
            div.className = "grid grid-cols-3 gap-2 bg-black/20 p-4 rounded-xl border border-gray-800 mt-2";
            div.innerHTML = `<input name="q[]" placeholder="Quality" class="input-field text-xs">
                             <input name="tg[]" placeholder="Telegram Link" class="input-field text-xs">
                             <input name="d[]" placeholder="Direct Link" class="input-field text-xs">`;
            document.getElementById('quality_inputs').appendChild(div);
        }
    </script>
</body>
</html>
"""

USER_HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <h1 class="text-2xl font-black text-red-600 italic tracking-tighter" onclick="location.href='/'">{{ conf.site_name }}</h1>
        <form class="hidden md:flex bg-gray-900/50 border border-gray-800 rounded-full px-4 py-1">
            <input name="s" placeholder="Search..." class="bg-transparent text-sm outline-none w-64">
            <button><i class="fa fa-search text-gray-500"></i></button>
        </form>
        <button onclick="document.getElementById('side').classList.toggle('hidden')"><i class="fa fa-bars text-xl"></i></button>
    </nav>
    <div id="side" class="hidden fixed inset-0 z-[60]">
        <div class="absolute inset-0 bg-black/95" onclick="this.parentElement.classList.add('hidden')"></div>
        <div class="absolute right-0 h-full w-80 glass p-10">
            <h2 class="text-2xl font-black text-red-600 mb-10 italic uppercase">Menu</h2>
            <div class="grid gap-6">
                <a href="/"><i class="fa fa-home mr-3 text-red-600"></i> Home</a>
                <div class="text-[10px] text-gray-600 uppercase font-black mt-4">Browse Categories</div>
                {% for c in cats %}<a href="/?s={{ c.name }}" class="text-sm font-bold">{{ c.name }}</a>{% endfor %}
                <hr class="border-gray-800"><a href="/admin/login" class="text-xs text-gray-600">Admin Login</a>
            </div>
        </div>
    </div>
    <div class="bg-red-600 text-white text-center py-1 text-[10px] font-black uppercase overflow-hidden"><marquee>{{ conf.header_notice }}</marquee></div>
    <main class="p-4 md:px-16">
        <div class="flex gap-4 overflow-x-auto no-scrollbar py-6">
            {% for m in slider %}
            <div class="min-w-[280px] md:min-w-[450px] h-44 md:h-64 relative rounded-[30px] overflow-hidden flex-shrink-0 cursor-pointer" onclick="location.href='/view/{{ m._id }}'">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover">
                <div class="absolute inset-0 bg-gradient-to-t from-black via-transparent p-6 flex flex-col justify-end">
                    <p class="font-black text-xl uppercase italic tracking-tighter">{{ m.title }}</p>
                    <span class="text-xs text-gray-400 font-bold">{{ m.year }} • {{ m.lang }}</span>
                </div>
            </div>
            {% endfor %}
        </div>
        <h2 class="text-2xl font-black mb-8 mt-12 border-l-8 border-red-600 pl-4 italic tracking-tighter uppercase">Recommended</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
            {% for m in items %}
            <div class="cursor-pointer group" onclick="location.href='/view/{{ m._id }}'">
                <div class="relative rounded-2xl overflow-hidden aspect-[2/3] border border-gray-800">
                    <img src="{{ m.poster }}" class="w-full h-full object-cover group-hover:scale-110 transition duration-500">
                </div>
                <div class="mt-3">
                    <h3 class="font-bold text-xs md:text-sm truncate uppercase italic tracking-tighter">{{ m.title }}</h3>
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
                <span>{{ m.year }}</span><span>{{ m.lang }}</span><span><i class="fa fa-eye"></i> {{ m.views }}</span>
            </div>
            <p class="text-gray-300 text-sm md:text-lg max-w-4xl italic mt-4">{{ m.story }}</p>
        </div>
    </div>

    <div class="p-6 md:p-20">
        {% if m.type == 'movie' %}
            <h3 class="text-2xl font-black mb-8 italic border-l-4 border-red-600 pl-4 uppercase">Watch Now</h3>
            <div class="grid gap-4 max-w-3xl">
                {% for l in m.movie_links %}
                <div class="glass p-5 rounded-2xl flex justify-between items-center">
                    <span class="font-black text-red-600 italic uppercase">{{ l.q }}</span>
                    <div class="flex gap-4">
                        {% if l.tg %}<a href="{{ l.tg }}" class="text-sky-500"><i class="fab fa-telegram text-2xl"></i></a>{% endif %}
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
                <div class="glass p-6 rounded-[30px]">
                    <div class="font-black text-[12px] text-gray-400 uppercase mb-4 tracking-widest">Episode {{ ep.en }}</div>
                    <div class="grid md:grid-cols-2 gap-4">
                        {% for l in ep.links %}
                        <div class="bg-gray-800/30 p-4 rounded-2xl flex justify-between items-center border border-white/5">
                            <span class="text-red-500 font-black italic text-sm">{{ l.q }}</span>
                            <div class="flex gap-4 items-center">
                                {% if l.tg %}<a href="{{ l.tg }}" class="text-sky-500 text-2xl" target="_blank"><i class="fab fa-telegram"></i></a>{% endif %}
                                <a href="{{ l.d }}" class="bg-white text-black px-4 py-2 rounded-xl text-[10px] font-black uppercase italic" target="_blank">Direct Link</a>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        {% endif %}

        {% if m.images %}
        <div class="mt-20">
            <h3 class="text-2xl font-black mb-8 italic border-l-4 border-red-600 pl-4 uppercase">Gallery & Screenshots</h3>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                {% for img in m.images %}
                <img src="{{ img }}" class="rounded-2xl border border-white/5 hover:scale-105 transition duration-300 cursor-pointer shadow-2xl">
                {% endfor %}
            </div>
        </div>
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

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Admin Login</title></head>
<body class="flex items-center justify-center min-h-screen p-6">
    <form method="POST" class="glass p-12 rounded-[60px] w-full max-w-lg text-center">
        <h2 class="text-4xl font-black text-red-600 mb-10 uppercase italic">Admin Portal</h2>
        <input name="u" placeholder="Admin Username" class="input-field mb-6 text-center" required>
        <input name="p" type="password" placeholder="Passcode" class="input-field mb-8 text-center" required>
        <button class="w-full btn-red py-4 rounded-3xl font-black uppercase tracking-widest">Login</button>
    </form>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
