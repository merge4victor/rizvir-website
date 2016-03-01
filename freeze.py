from flask_frozen import Freezer
from rizvir import app, CONTENT_PATH
import os

freezer = Freezer(app)

# Go through the filesystem to find content (usually article images)
# for the article_content() function:
@freezer.register_generator
# route('/articles/<id>/<content>')
def article_content():
	# We don't really need to recurse:
	articles = os.listdir( os.path.join(CONTENT_PATH, 'articles') )
	for articleid in articles:
		for filename in os.listdir( os.path.join(CONTENT_PATH, 'articles', articleid) ):
			if filename in ['README.md', 'metadata']:
				continue
			yield {'id': articleid, 'content': filename }

if __name__ == '__main__':
	freezer.freeze()
	#freezer.run(debug=True)

