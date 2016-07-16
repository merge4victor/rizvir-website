
module.exports = function(grunt) {

		grunt.initConfig({
			pkg: grunt.file.readJSON('package.json'),
			shell: {
				freezeFlask: {
					command: 'python freeze.py'
				}
			}
		});

		require('load-grunt-tasks')(grunt);
		grunt.registerTask('default', ['shell']);
};
