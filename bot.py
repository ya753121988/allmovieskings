import os
import requests
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "ULTIMATE_DRAMA_STORE_FIXED_FINAL_V4"

# --- ডাটাবেজ এবং API কনফিগারেশন ---
MONGO_URI = "mongodb+srv://drama:drama@cluster0.sa4kvgu.mongodb.net/DramaStoreDB?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

client = MongoClient(MONGO_URI)
db = client['DramaStoreB']
contents_col = db['contents']
settings_col = db['site_settings']
cat_col = db['categories']

# ডিফল্ট সেটিংস চেক (অ্যাড সেটিংসসহ)
if not settings_col.find_one({"id": "config"}):
    settings_col.insert_one({
        "id": "config", "site_name": "DRAMA-FLIX", "site_logo": "https://i.ibb.co/logo.png",
        "header_notice": "Welcome to Premium Drama Store", "admin_user": "admin", "admin_pass": "1234",
        "movie_limit": 20, "series_limit": 20, "slider_limit": 10,
        "ad_status": "off", "ad_timer": 5, "direct_ad_link": "",
        "popunder_ad": "", "social_bar_ad": "", "header_ad": "", "footer_ad": "", "middle_ad": ""
    })

# --- UI CSS ---
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
    #adminSidebar { position: fixed; top: 0; left: -100%; height: 100%; width: 280px; z-index: 2000; transition: 0.4s; background: #0f172a; border-right: 1px solid #1e293b; overflow-y: auto; }
    #adminSidebar.active { left: 0; }
    @media (min-width: 1024px) { #adminSidebar { position: sticky; left: 0; width: 320px; } .menu-toggle { display: none; } }
    .nav-link { display: flex; align-items: center; padding: 14px; border-radius: 12px; color: #94a3b8; margin-bottom: 5px; transition: 0.3s; }
    .nav-link:hover, .nav-link.active { background: var(--p); color: white; }
    
    /* Ad Overlay */
    #ad-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.9); z-index:9999; flex-direction:column; align-items:center; justify-content:center; }
</style>
"""

# --- AD INTERCEPTOR SCRIPT ---
AD_JS = """
<script>
    function handleLink(e, mainUrl) {
        const adStatus = "{{ conf.ad_status }}";
        const adLink = "{{ conf.direct_ad_link }}";
        const timer = parseInt("{{ conf.ad_timer }}");
        
        if (adStatus === "on" && adLink) {
            e.preventDefault();
            const overlay = document.getElementById('ad-overlay');
            overlay.style.display = 'flex';
            window.open(adLink, '_blank');
            let count = timer;
            const btn = document.getElementById('ad-timer-btn');
            const interval = setInterval(() => {
                btn.innerText = "Please Wait " + count + "s";
                count--;
                if (count < 0) {
                    clearInterval(interval);
                    btn.innerText = "Go to Content";
                    btn.onclick = () => { window.location.href = mainUrl; };
                    btn.classList.add('bg-green-600');
                }
            }, 1000);
        } else {
            window.location.href = mainUrl;
        }
    }
</script>
<div id="ad-overlay">
    <div class="text-center p-10 glass rounded-3xl">
        <h2 class="text-2xl font-bold mb-4">Redirecting to Content...</h2>
        <button id="ad-timer-btn" class="btn-red px-10 py-4">Waiting...</button>
    </div>
</div>
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
    return render_template_string(USER_HOME_HTML, ui=UI_HEAD, conf=conf, items=items, slider=slider, cats=cats, ad_js=AD_JS)

@app.route('/view/<id>')
def view(id):
    item = contents_col.find_one({"_id": ObjectId(id)})
    contents_col.update_one({"_id": ObjectId(id)}, {"$inc": {"views": 1}})
    conf = settings_col.find_one({"id": "config"})
    return render_template_string(USER_DETAIL_HTML, ui=UI_HEAD, m=item, conf=conf, ad_js=AD_JS)

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
        data.update({"views": 0, "movie_links": [], "seasons": []})
        contents_col.insert_one(data)
    return redirect('/admin/manage')

@app.route('/admin/manage')
def admin_manage():
    if not session.get('admin'): return redirect('/admin/login')
    q = request.args.get('q', '')
    items = list(contents_col.find({"title": {"$regex": q, "$options": "i"}}).sort("_id", -1))
    return render_template_string(ADMIN_MANAGE_HTML, ui=UI_HEAD, items=items, q=q)

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

# --- MOVIE LINKS & SERIES MANAGEMENT ---
@app.route('/admin/links/<id>', methods=['GET', 'POST'])
def manage_links(id):
    if not session.get('admin'): return redirect('/admin/login')
    if request.method == 'POST':
        action = request.form.get('action')
        lid = request.form.get('lid', str(ObjectId()))
        if action in ['add', 'edit']:
            link = {"id": lid, "q": request.form.get('q'), "tg": request.form.get('tg'), "d": request.form.get('d')}
            if action == 'add':
                contents_col.update_one({"_id": ObjectId(id)}, {"$push": {"movie_links": link}})
            else:
                contents_col.update_one({"_id": ObjectId(id), "movie_links.id": lid}, {"$set": {"movie_links.$": link}})
        elif action == 'delete':
            contents_col.update_one({"_id": ObjectId(id)}, {"$pull": {"movie_links": {"id": request.form.get('lid')}}})
    item = contents_col.find_one({"_id": ObjectId(id)})
    return render_template_string(ADMIN_LINKS_HTML, ui=UI_HEAD, m=item)

@app.route('/admin/series/<id>', methods=['GET', 'POST'])
def manage_series(id):
    if not session.get('admin'): return redirect('/admin/login')
    if request.method == 'POST':
        action = request.form.get('action')
        sn = request.form.get('sn')
        if action in ['add_ep', 'edit_ep']:
            eid = request.form.get('eid', str(ObjectId()))
            qualities, tg_links, d_links = request.form.getlist('q[]'), request.form.getlist('tg[]'), request.form.getlist('d[]')
            links_list = [{"q": qualities[i], "tg": tg_links[i], "d": d_links[i]} for i in range(len(qualities)) if qualities[i]]
            ep = {"id": eid, "en": request.form.get('en'), "links": links_list}
            
            if action == 'add_ep':
                res = contents_col.update_one({"_id": ObjectId(id), "seasons.sn": sn}, {"$push": {"seasons.$.eps": ep}})
                if res.matched_count == 0: contents_col.update_one({"_id": ObjectId(id)}, {"$push": {"seasons": {"sn": sn, "eps": [ep]}}})
            else:
                contents_col.update_one({"_id": ObjectId(id), "seasons.sn": sn, "seasons.eps.id": eid}, {"$set": {"seasons.$.eps.$[elem]": ep}}, array_filters=[{"elem.id": eid}])
        elif action == 'del_ep':
            contents_col.update_one({"_id": ObjectId(id), "seasons.sn": sn}, {"$pull": {"seasons.$.eps": {"id": request.form.get('eid')}}})
        elif action == 'del_season':
            contents_col.update_one({"_id": ObjectId(id)}, {"$pull": {"seasons": {"sn": sn}}})
    item = contents_col.find_one({"_id": ObjectId(id)})
    return render_template_string(ADMIN_SERIES_HTML, ui=UI_HEAD, m=item)

# --- SETTINGS & ADS ---
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

# --- TMDB API ---
@app.route('/api/tmdb_search')
def api_tmdb_search():
    q = request.args.get('q'); t = request.args.get('t', 'movie')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/{t}?api_key={TMDB_API_KEY}&query={q}").json())

@app.route('/api/tmdb_info')
def api_tmdb_info():
    tid, t = request.args.get('id'), request.args.get('t')
    res = requests.get(f"https://api.themoviedb.org/3/{t}/{tid}?api_key={TMDB_API_KEY}&append_to_response=images").json()
    logos = res.get('images', {}).get('logos', [])
    gallery = [f"https://image.tmdb.org/t/p/original{b['file_path']}" for b in res.get('images', {}).get('backdrops', [])[:10]]
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
        <a href="/admin/settings" class="nav-link"><i class="fa fa-cog w-8"></i> Site & Ad Settings</a>
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
                <input name="title" id="f_title" value="{{ edit.title if edit else '' }}" placeholder="Title" class="input-field mb-4" required>
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <input name="year" id="f_year" value="{{ edit.year if edit else '' }}" placeholder="Year" class="input-field">
                    <input name="lang" id="f_lang" value="{{ edit.lang if edit else '' }}" placeholder="Language" class="input-field">
                </div>
                <input name="poster" id="f_poster" value="{{ edit.poster if edit else '' }}" placeholder="Poster URL" class="input-field mb-2">
                <input name="backdrop" id="f_backdrop" value="{{ edit.backdrop if edit else '' }}" placeholder="Backdrop URL" class="input-field mb-2">
                <input name="logo" id="f_logo" value="{{ edit.logo if edit else '' }}" placeholder="Logo URL" class="input-field">
            </div>
            <div>
                <div class="grid grid-cols-2 gap-2 bg-black/40 p-4 rounded-2xl h-32 overflow-y-auto mb-4 border border-gray-800">
                    {% for c in cats %}<label class="text-xs"><input type="checkbox" name="cats" value="{{ c.name }}" {{ 'checked' if edit and c.name in edit.category else '' }}> {{ c.name }}</label>{% endfor %}
                </div>
                <textarea name="story" id="f_story" placeholder="Storyline..." class="input-field h-32">{{ edit.story if edit else '' }}</textarea>
                <button class="w-full btn-red py-4 mt-6 uppercase font-black">{{ 'Update' if edit else 'Save' }} Content</button>
            </div>
        </form>
    </div>
    <script>
        async function searchTMDB(){
            const q = document.getElementById('tmdb_q').value, t = document.getElementById('tmdb_type').value;
            const res = await fetch(`/api/tmdb_search?q=${q}&t=${t}`);
            const data = await res.json();
            const div = document.getElementById('results'); div.innerHTML = '';
            data.results.forEach(m => { div.innerHTML += `<div class="min-w-[120px] cursor-pointer" onclick="fill('${m.id}', '${t}')"><img src="https://image.tmdb.org/t/p/w200${m.poster_path}" class="rounded-xl border-2 border-transparent hover:border-red-600 transition"></div>`; });
        }
        async function fill(id, type){
            const res = await fetch(`/api/tmdb_info?id=${id}&t=${type}`);
            const j = await res.json(); const d = j.data;
            document.getElementById('f_title').value = d.title || d.name;
            document.getElementById('f_year').value = (d.release_date || d.first_air_date || '').split('-')[0];
            document.getElementById('f_lang').value = (d.original_language || '').toUpperCase();
            document.getElementById('f_poster').value = 'https://image.tmdb.org/t/p/w500' + d.poster_path;
            document.getElementById('f_backdrop').value = 'https://image.tmdb.org/t/p/original' + d.backdrop_path;
            document.getElementById('f_logo').value = j.logo; document.getElementById('f_gallery').value = j.gallery;
            document.getElementById('f_story').value = d.overview; document.getElementById('f_type').value = type; alert("Loaded!");
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
    """ + SIDEBAR_HTML + """
    <div class="flex-1 p-4 md:p-10">
        <form class="flex mb-8 bg-gray-900 rounded-full px-4 border border-gray-800">
            <input name="q" value="{{ q }}" placeholder="Search content..." class="bg-transparent p-4 outline-none w-full">
            <button><i class="fa fa-search"></i></button>
        </form>
        <div class="grid gap-4">
            {% for m in items %}
            <div class="glass p-4 rounded-3xl flex items-center justify-between">
                <div class="flex items-center gap-4">
                    <img src="{{ m.poster }}" class="h-16 w-12 rounded-lg object-cover">
                    <div><h4 class="font-bold">{{ m.title }}</h4><span class="text-xs text-gray-500 uppercase">{{ m.type }}</span></div>
                </div>
                <div class="flex gap-2">
                    <a href="/admin/dashboard?edit={{ m._id }}" class="bg-blue-600 p-3 rounded-xl"><i class="fa fa-edit"></i></a>
                    <a href="/admin/{{ 'links' if m.type=='movie' else 'series' }}/{{ m._id }}" class="bg-indigo-600 p-3 rounded-xl"><i class="fa fa-link"></i></a>
                    <a href="/admin/delete/{{ m._id }}" class="bg-red-800 p-3 rounded-xl" onclick="return confirm('Delete?')"><i class="fa fa-trash"></i></a>
                </div>
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
<head>{{ ui|safe }}<title>Settings & Ads</title></head>
<body class="flex flex-col lg:flex-row min-h-screen">
    """ + SIDEBAR_HTML + """
    <div class="flex-1 p-6 md:p-12 max-w-5xl">
        <h2 class="text-2xl font-black mb-10 italic">SITE & AD CONFIGURATION</h2>
        <form method="POST" class="glass p-8 rounded-[40px] space-y-6">
            <div class="grid md:grid-cols-2 gap-6">
                <div><label class="text-xs font-bold text-gray-500">Site Name</label><input name="site_name" value="{{ conf.site_name }}" class="input-field"></div>
                <div><label class="text-xs font-bold text-gray-500">Logo URL</label><input name="site_logo" value="{{ conf.site_logo }}" class="input-field"></div>
            </div>
            <div class="bg-red-900/10 p-6 rounded-3xl border border-red-600/20">
                <h3 class="text-red-600 font-bold mb-4 uppercase italic">Direct Link Ad Settings</h3>
                <div class="grid md:grid-cols-3 gap-4 mb-4">
                    <select name="ad_status" class="input-field"><option value="on" {{ 'selected' if conf.ad_status=='on' }}>Ad Status: ON</option><option value="off" {{ 'selected' if conf.ad_status=='off' }}>Ad Status: OFF</option></select>
                    <input name="ad_timer" type="number" value="{{ conf.ad_timer }}" placeholder="Timer (Sec)" class="input-field">
                    <input name="direct_ad_link" value="{{ conf.direct_ad_link }}" placeholder="Ad URL" class="input-field">
                </div>
            </div>
            <div class="grid md:grid-cols-2 gap-4">
                <div><label class="text-xs text-gray-500">Popunder Ad Script</label><textarea name="popunder_ad" class="input-field h-24">{{ conf.popunder_ad }}</textarea></div>
                <div><label class="text-xs text-gray-500">Social Bar Script</label><textarea name="social_bar_ad" class="input-field h-24">{{ conf.social_bar_ad }}</textarea></div>
                <div><label class="text-xs text-gray-500">Header Ad (HTML)</label><textarea name="header_ad" class="input-field h-24">{{ conf.header_ad }}</textarea></div>
                <div><label class="text-xs text-gray-500">Footer Ad (HTML)</label><textarea name="footer_ad" class="input-field h-24">{{ conf.footer_ad }}</textarea></div>
                <div class="col-span-2"><label class="text-xs text-gray-500">Middle Ad (HTML)</label><textarea name="middle_ad" class="input-field h-24">{{ conf.middle_ad }}</textarea></div>
            </div>
            <button class="w-full btn-red py-4 uppercase font-black">Save Settings</button>
        </form>
    </div>
</body>
</html>
"""

ADMIN_LINKS_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Manage Movie Links</title></head>
<body class="p-6">
    <div class="max-w-4xl mx-auto glass p-8 rounded-[40px]">
        <h2 class="text-2xl font-black mb-8 italic">MANAGE LINKS: {{ m.title }}</h2>
        <form method="POST" id="linkForm" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
            <input type="hidden" name="action" id="action" value="add">
            <input type="hidden" name="lid" id="lid" value="">
            <input name="q" id="q" placeholder="Quality" class="input-field" required>
            <input name="tg" id="tg" placeholder="TG Link" class="input-field">
            <input name="d" id="d" placeholder="Direct Link" class="input-field" required>
            <button class="btn-red" id="submitBtn">ADD</button>
        </form>
        <div class="space-y-3">
            {% for l in m.movie_links %}
            <div class="bg-black/40 p-4 rounded-2xl flex justify-between items-center">
                <span class="font-bold text-red-600">{{ l.q }}</span>
                <div class="flex gap-4">
                    <button onclick="editLink('{{ l.id }}','{{ l.q }}','{{ l.tg }}','{{ l.d }}')" class="text-blue-400"><i class="fa fa-edit"></i></button>
                    <form method="POST" style="display:inline"><input type="hidden" name="action" value="delete"><input type="hidden" name="lid" value="{{ l.id }}"><button class="text-red-600"><i class="fa fa-trash"></i></button></form>
                </div>
            </div>
            {% endfor %}
        </div>
        <a href="/admin/manage" class="block text-center mt-6 text-gray-500">Back</a>
    </div>
    <script>
        function editLink(id, q, tg, d) {
            document.getElementById('action').value = 'edit';
            document.getElementById('lid').value = id;
            document.getElementById('q').value = q;
            document.getElementById('tg').value = tg;
            document.getElementById('d').value = d;
            document.getElementById('submitBtn').innerText = 'UPDATE';
        }
    </script>
</body>
</html>
"""

ADMIN_SERIES_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}<title>Series Manager</title></head>
<body class="p-6">
    <div class="max-w-5xl mx-auto glass p-8 rounded-[40px]">
        <h2 class="text-2xl font-black mb-8 italic uppercase">Series Manager: {{ m.title }}</h2>
        <form method="POST" id="epForm" class="bg-white/5 p-6 rounded-3xl mb-8">
            <input type="hidden" name="action" id="action" value="add_ep">
            <input type="hidden" name="eid" id="eid" value="">
            <div class="grid grid-cols-2 gap-4 mb-4">
                <input name="sn" id="sn" placeholder="Season No" class="input-field" required>
                <input name="en" id="en" placeholder="Episode No" class="input-field" required>
            </div>
            <div id="quality_inputs" class="space-y-2">
                <div class="grid grid-cols-3 gap-2"><input name="q[]" placeholder="Quality" class="input-field"><input name="tg[]" placeholder="TG Link" class="input-field"><input name="d[]" placeholder="Direct Link" class="input-field"></div>
            </div>
            <button type="button" onclick="addMoreQual()" class="text-blue-400 text-xs mt-2">+ MORE QUALITY</button>
            <button class="w-full btn-red mt-6" id="submitBtn">SAVE EPISODE</button>
        </form>
        {% for s in m.seasons %}
        <div class="mb-6 p-6 glass rounded-3xl">
            <div class="flex justify-between mb-4"><h3 class="font-black text-red-600">Season {{ s.sn }}</h3><form method="POST"><input type="hidden" name="action" value="del_season"><input type="hidden" name="sn" value="{{ s.sn }}"><button class="text-xs text-red-600">Delete Season</button></form></div>
            <div class="grid gap-2">
                {% for ep in s.eps %}
                <div class="bg-black/20 p-3 rounded-xl flex justify-between items-center">
                    <span>Episode {{ ep.en }}</span>
                    <div class="flex gap-4">
                        <button onclick='editEp("{{ s.sn }}","{{ ep.en }}","{{ ep.id }}", {{ ep.links|tojson }})' class="text-blue-400"><i class="fa fa-edit"></i></button>
                        <form method="POST"><input type="hidden" name="action" value="del_ep"><input type="hidden" name="sn" value="{{ s.sn }}"><input type="hidden" name="eid" value="{{ ep.id }}"><button class="text-red-600"><i class="fa fa-trash"></i></button></form>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
        <a href="/admin/manage" class="block text-center text-gray-500">Back</a>
    </div>
    <script>
        function addMoreQual(q="", t="", d=""){
            const div = document.createElement('div'); div.className="grid grid-cols-3 gap-2 mt-2";
            div.innerHTML = `<input name="q[]" value="${q}" class="input-field"><input name="tg[]" value="${t}" class="input-field"><input name="d[]" value="${d}" class="input-field">`;
            document.getElementById('quality_inputs').appendChild(div);
        }
        function editEp(sn, en, eid, links){
            document.getElementById('action').value = 'edit_ep';
            document.getElementById('eid').value = eid;
            document.getElementById('sn').value = sn;
            document.getElementById('en').value = en;
            document.getElementById('quality_inputs').innerHTML = '';
            links.forEach(l => addMoreQual(l.q, l.tg, l.d));
            document.getElementById('submitBtn').innerText = 'UPDATE EPISODE';
        }
    </script>
</body>
</html>
"""

USER_HOME_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}{{ conf.popunder_ad|safe }}{{ conf.social_bar_ad|safe }}<title>{{ conf.site_name }}</title></head>
<body>
    {{ ad_js|safe }}
    <nav class="p-4 glass sticky top-0 z-50 flex justify-between items-center px-6">
        <h1 class="text-2xl font-black text-red-600 italic cursor-pointer" onclick="location.href='/'">{{ conf.site_name }}</h1>
        <form class="hidden md:flex bg-gray-900 border border-gray-800 rounded-full px-4"><input name="s" placeholder="Search..." class="bg-transparent p-2 outline-none w-64"><button><i class="fa fa-search text-gray-500"></i></button></form>
        <button onclick="document.getElementById('side').classList.toggle('hidden')"><i class="fa fa-bars text-xl"></i></button>
    </nav>
    <div id="side" class="hidden fixed inset-0 z-[60]"><div class="absolute inset-0 bg-black/95" onclick="this.parentElement.classList.add('hidden')"></div><div class="absolute right-0 h-full w-80 glass p-10"><h2 class="text-2xl font-black text-red-600 mb-10">MENU</h2>{% for c in cats %}<a href="/?s={{ c.name }}" class="block mb-4 font-bold">{{ c.name }}</a>{% endfor %}<hr class="border-gray-800 my-6"><a href="/admin/login" class="text-xs">Admin Login</a></div></div>
    
    <div class="flex justify-center my-4">{{ conf.header_ad|safe }}</div>
    <div class="bg-red-600 text-white text-center py-1 text-[10px] font-black uppercase"><marquee>{{ conf.header_notice }}</marquee></div>

    <main class="p-4 md:px-16">
        <div class="flex gap-4 overflow-x-auto no-scrollbar py-6">
            {% for m in slider %}
            <div class="min-w-[280px] md:min-w-[450px] h-44 md:h-64 relative rounded-[30px] overflow-hidden cursor-pointer" onclick="handleLink(event, '/view/{{ m._id }}')">
                <img src="{{ m.backdrop }}" class="w-full h-full object-cover">
                <div class="absolute inset-0 bg-gradient-to-t from-black p-6 flex flex-col justify-end"><p class="font-black text-xl italic uppercase">{{ m.title }}</p></div>
            </div>
            {% endfor %}
        </div>
        
        <div class="flex justify-center my-8">{{ conf.middle_ad|safe }}</div>

        <h2 class="text-2xl font-black mb-8 border-l-8 border-red-600 pl-4 italic uppercase">Recommended</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
            {% for m in items %}
            <div class="cursor-pointer group" onclick="handleLink(event, '/view/{{ m._id }}')">
                <div class="relative rounded-2xl overflow-hidden aspect-[2/3] border border-gray-800"><img src="{{ m.poster }}" class="w-full h-full object-cover group-hover:scale-110 transition"></div>
                <h3 class="mt-3 font-bold text-xs md:text-sm truncate uppercase">{{ m.title }}</h3>
            </div>
            {% endfor %}
        </div>
    </main>
    <div class="flex justify-center mt-10">{{ conf.footer_ad|safe }}</div>
</body>
</html>
"""

USER_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>{{ ui|safe }}{{ conf.popunder_ad|safe }}{{ conf.social_bar_ad|safe }}<title>{{ m.title }}</title></head>
<body>
    {{ ad_js|safe }}
    <div class="relative h-[60vh] md:h-[80vh]">
        <img src="{{ m.backdrop }}" class="w-full h-full object-cover opacity-30">
        <div class="absolute inset-0 bg-gradient-to-t from-[#05070a]"></div>
        <button onclick="history.back()" class="absolute top-8 left-8 glass h-12 w-12 rounded-full"><i class="fa fa-arrow-left"></i></button>
        <div class="absolute bottom-12 left-6 md:left-20">
            {% if m.logo %}<img src="{{ m.logo }}" class="w-64 md:w-96 mb-6">{% else %}<h1 class="text-5xl md:text-8xl font-black italic uppercase">{{ m.title }}</h1>{% endif %}
            <p class="text-gray-300 max-w-4xl italic mt-4">{{ m.story }}</p>
        </div>
    </div>
    <div class="p-6 md:p-20">
        <div class="flex justify-center mb-10">{{ conf.middle_ad|safe }}</div>
        {% if m.type == 'movie' %}
            <h3 class="text-2xl font-black mb-8 italic border-l-4 border-red-600 pl-4 uppercase">Watch Now</h3>
            <div class="grid gap-4 max-w-3xl">
                {% for l in m.movie_links %}
                <div class="glass p-5 rounded-2xl flex justify-between items-center">
                    <span class="font-black text-red-600 uppercase">{{ l.q }}</span>
                    <div class="flex gap-4">
                        {% if l.tg %}<a href="{{ l.tg }}" class="text-sky-500"><i class="fab fa-telegram text-2xl"></i></a>{% endif %}
                        <a href="#" onclick="handleLink(event, '{{ l.d }}')" class="bg-white text-black px-6 py-2 rounded-xl font-black text-xs uppercase">Download</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <div class="flex gap-6 border-b border-gray-900 mb-10 overflow-x-auto no-scrollbar">{% for s in m.seasons %}<button onclick="showS('{{ s.sn }}')" class="s-tab px-6 py-4 uppercase font-black italic" id="btn-{{ s.sn }}">Season {{ s.sn }}</button>{% endfor %}</div>
            {% for s in m.seasons %}
            <div class="s-content hidden grid gap-6" id="box-{{ s.sn }}">
                {% for ep in s.eps %}
                <div class="glass p-6 rounded-[30px]">
                    <div class="font-black text-xs text-gray-400 mb-4">EPISODE {{ ep.en }}</div>
                    <div class="grid md:grid-cols-2 gap-4">
                        {% for l in ep.links %}
                        <div class="bg-gray-800/30 p-4 rounded-2xl flex justify-between items-center border border-white/5">
                            <span class="text-red-500 font-black">{{ l.q }}</span>
                            <div class="flex gap-4 items-center">
                                {% if l.tg %}<a href="{{ l.tg }}" class="text-sky-500 text-2xl"><i class="fab fa-telegram"></i></a>{% endif %}
                                <a href="#" onclick="handleLink(event, '{{ l.d }}')" class="bg-white text-black px-4 py-2 rounded-xl text-xs font-black">Direct Link</a>
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
            <h3 class="text-2xl font-black mb-8 italic border-l-4 border-red-600 pl-4 uppercase">Gallery</h3>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4">{% for img in m.images %}<img src="{{ img }}" onclick="handleLink(event, '{{ img }}')" class="rounded-2xl cursor-pointer hover:scale-105 transition shadow-2xl">{% endfor %}</div>
        </div>
        {% endif %}
    </div>
    <div class="flex justify-center mt-10">{{ conf.footer_ad|safe }}</div>
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
<body class="flex items-center justify-center min-h-screen">
    <form method="POST" class="glass p-12 rounded-[60px] w-full max-w-md text-center">
        <h2 class="text-3xl font-black text-red-600 mb-8 uppercase italic">Admin Portal</h2>
        <input name="u" placeholder="Username" class="input-field mb-6 text-center" required>
        <input name="p" type="password" placeholder="Passcode" class="input-field mb-8 text-center" required>
        <button class="w-full btn-red py-4 uppercase font-black">Login</button>
    </form>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
