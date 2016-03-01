from __future__ import print_function
from flask import Flask, url_for, render_template, Markup, send_from_directory, redirect, request
import os
import sys
import ConfigParser
import markdown

app = Flask(__name__)

CURRENT_PATH = os.path.abspath(os.path.dirname(__file__))
CONTENT_PATH = os.path.join(CURRENT_PATH, 'static/content')
PHOTO_PATH = os.path.join(CURRENT_PATH, 'static/files/photos')
CACHE_TIMEOUT = 604800

# Traverse the /content/ directory at startup
# rather than with every page load, and create a
# dict with all the content details
# Articles and Code are treated similarly
# So we'll keep a structure like:
# content_metadata = { 'articles' => {'id1'=>{author,url,etc}}, {'id2'=> ... } 
#		               'code' => {'id1'=>{author,url,etc},  } }

content_metadata = {}
for type in [ 'articles', 'code' ]:
	content_dir_path = os.path.join(CONTENT_PATH, type)
	content_dirs = os.listdir(content_dir_path)

	final_dict = {}
	# For each dir here, read the metadata file
	for content_dir in content_dirs:
		content_dict = {}
		config = ConfigParser.ConfigParser()
		metadata_path = os.path.join(content_dir_path, content_dir, 'metadata')
		if not os.path.isfile(metadata_path):
			print("Could not read metadata file: {0}".format(metadata_path), file=sys.stderr)
			continue
		config.read( metadata_path )
		content_id = content_dir
		for key in [ 'title', 'author', 'last_updated', 'written_on', 'distributions', 'description', 'url' ]:
			try:
				content_dict[key] = config.get('metadata', key)
			except:
				content_dict[key] = ""
		final_dict[content_id] = content_dict
	content_metadata[type] = final_dict

@app.route('/')
def index():
	return redirect(url_for('articles'))

@app.route('/articles/')
def articles():
	return render_template('articles.html', metadata = content_metadata['articles'])

@app.route('/code/')
def code():
	return render_template('code.html', metadata = content_metadata['code'])

@app.route('/articles/<id>')
@app.route('/articles/<id>/')
def article(id):

	# First see if the id exists in our bootup metadata scan:
	if not id in content_metadata['articles']:
			return "404", 404

	# The above test should be enough, but just in case (since it involves the filesystem):
	id = id.replace("..","")

	# Get the absolute path to the README.md file 
	readme_path = os.path.join(CONTENT_PATH, 'articles', id, 'README.md')

	# Triple check the id, by seeing if the resulting path is in CONTENT_PATH
	if not os.path.realpath(readme_path).startswith(CONTENT_PATH):
		return "Forbidden", 403

	# Read file
	readme_f = open(readme_path, 'r')

	# Generate markdown HTML
	content = Markup( markdown.markdown( text = readme_f.read(), extensions = [
		'markdown.extensions.nl2br', 'markdown.extensions.extra', 'markdown.extensions.codehilite' ],
		extension_configs = { 'markdown.extensions.codehilite': {
					'guess_lang': False }} ))
	readme_f.close()

	return render_template('article-display.html', 
		content = content, 
		metadata = content_metadata['articles'][id], 
	)


# This is for images and files kept in the article dir
# referenced with relative links in the markdown
@app.route('/articles/<id>/<content>')
def article_content(id, content):

	if not id in content_metadata['articles']:
			return "404", 404

	id = id.replace("..","")

	# send_from_directory does the is-file-in-content-path check automatically:
	return send_from_directory( os.path.join(CONTENT_PATH, 'articles'), os.path.join(id, content), cache_timeout=CACHE_TIMEOUT )


# Photos
@app.route('/photos/')
def photos():
	thumbnails = 'thumbnails'
	# Get a list of filenames from the photopath
	photos = os.listdir(PHOTO_PATH);
	photos.remove(thumbnails);
	photos.sort();
	photo_relative_path = 'files/photos'
	photo_thumbnails_relative_path = 'files/photos/' + thumbnails
	return render_template('photos.html', photos=enumerate(photos), 
		photo_relative_path=photo_relative_path, 
		photo_thumbnails_relative_path=photo_thumbnails_relative_path)

# Contact page
@app.route('/contact/')
def contact():
	return render_template('contact.html')


# Static files
@app.route('/robots.txt')
def static_files():
	return send_from_directory(app.static_folder, request.path[1:])

if __name__ == '__main__':
	app.debug = True
	app.run(host='0.0.0.0')

