function sessionsListApp() {
    return {
        sessions: [],
        dataDir: '',
        showUploadSection: false,
        uploadFile: null,
        uploading: false,
        uploadError: null,
        maxUploadBytes: null,

        async init() {
            await this.loadSessions();
        },

        async loadSessions() {
            try {
                const response = await fetch('/api/sessions');
                const data = await response.json();
                this.sessions = data.sessions || [];
                this.dataDir = data.data_dir || '';
                this.maxUploadBytes = data.max_upload_bytes || null;
            } catch (error) {
                console.error('Failed to load sessions:', error);
            }
        },

        uploadTooLargeMessage() {
            const limit = this.maxUploadBytes
                ? `the ${Math.round(this.maxUploadBytes / (1024 * 1024))} MB upload limit`
                : 'the upload limit';
            return `This file is larger than ${limit}. Restart Finchvox with a higher --max-upload-mb to allow it.`;
        },

        async uploadSession() {
            if (!this.uploadFile) return;

            // Checked here too because the server stops reading an oversized
            // upload, which browsers can report as a network error.
            if (this.maxUploadBytes && this.uploadFile.size > this.maxUploadBytes) {
                this.uploadError = this.uploadTooLargeMessage();
                return;
            }

            this.uploading = true;
            this.uploadError = null;

            try {
                const formData = new FormData();
                formData.append('file', this.uploadFile);

                const response = await fetch('/api/sessions/upload', {
                    method: 'POST',
                    body: formData
                });

                if (response.status === 413) {
                    throw new Error(this.uploadTooLargeMessage());
                }

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Upload failed');
                }

                window.location.href = `/sessions/${data.session_id}`;
            } catch (error) {
                this.uploadError = error.message;
            } finally {
                this.uploading = false;
            }
        },

        formatDuration(milliseconds) {
            if (!milliseconds) return '-';
            return formatDuration(milliseconds, 0);
        },

        formatCount(count) {
            return (count && count > 0) ? count.toLocaleString() : '—';
        }
    };
}
