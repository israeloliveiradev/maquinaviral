// Target and Simulator Dimensions (Default to 16:9)
let targetWidth = 1920;
let targetHeight = 1080;
let simWidth = 480;
let simHeight = 270;
let scaleX = simWidth / targetWidth; // 0.25
let scaleY = simHeight / targetHeight; // 0.25

// Elements Selection
const cropBox = document.getElementById('crop-box');
const simulator = document.getElementById('canvas-simulator');
const inputX = document.getElementById('coord-x');
const inputY = document.getElementById('coord-y');
const inputW = document.getElementById('coord-w');
const inputH = document.getElementById('coord-h');
const renderForm = document.getElementById('render-form');
const btnLoadTest = document.getElementById('btn-load-test');
const btnClearHistory = document.getElementById('btn-clear-history');
const batchesList = document.getElementById('batches-list');
const emptyState = document.getElementById('empty-state');

// Resolution Selection Elements
const resolutionPreset = document.getElementById('resolution-preset');
const customResGroup = document.getElementById('custom-res-group');
const resWidth = document.getElementById('res-width');
const resHeight = document.getElementById('res-height');

// Video Upload Selection Elements
const dropzone = document.getElementById('upload-dropzone');
const uploadInput = document.getElementById('video-upload-input');
const progressList = document.getElementById('upload-progress-list');
const videoSourcesInput = document.getElementById('video-sources');

// Template Upload Selection Elements
const templateUploadInput = document.getElementById('template-upload-input');
const btnUploadTemplate = document.getElementById('btn-upload-template');
const templateUploadProgress = document.getElementById('template-upload-progress');
const templateIdInput = document.getElementById('template-id');
const templatePreviewOverlay = document.getElementById('template-preview-overlay');

// Source Video Crop Selection Elements
const enableSourceCrop = document.getElementById('enable-source-crop');
const sourceCropSection = document.getElementById('source-crop-section');
const sourceVideoPreview = document.getElementById('source-video-preview');
const sourceCropBox = document.getElementById('source-crop-box');
const sourceSimulator = document.getElementById('source-simulator');
const inputSrcX = document.getElementById('src-coord-x');
const inputSrcY = document.getElementById('src-coord-y');
const inputSrcW = document.getElementById('src-coord-w');
const inputSrcH = document.getElementById('src-coord-h');

// Modal Elements
const videoModal = document.getElementById('video-modal');
const modalVideoPlayer = document.getElementById('modal-video-player');
const modalVideoTitle = document.getElementById('modal-video-title');
const modalVideoPath = document.getElementById('modal-video-path');
const modalClose = document.getElementById('modal-close');

// Active polling list
let activePollings = {};

// ==========================================
// 1. Dynamic Aspect Ratio Adjustments
// ==========================================

function adjustSimulatorAspect() {
    const preset = resolutionPreset.value;
    
    if (preset === '16:9') {
        targetWidth = 1920;
        targetHeight = 1080;
        customResGroup.style.display = 'none';
    } else if (preset === '9:16') {
        targetWidth = 1080;
        targetHeight = 1920;
        customResGroup.style.display = 'none';
    } else if (preset === '1:1') {
        targetWidth = 1080;
        targetHeight = 1080;
        customResGroup.style.display = 'none';
    } else if (preset === 'custom') {
        targetWidth = Math.max(10, parseInt(resWidth.value) || 1080);
        targetHeight = Math.max(10, parseInt(resHeight.value) || 1920);
        customResGroup.style.display = 'block';
    }

    // Keep simulator inside a max bounding box of 480px width, 270px height
    const maxW = 480;
    const maxH = 270;
    const targetAR = targetWidth / targetHeight;
    const maxAR = maxW / maxH; // 1.777...

    if (targetAR > maxAR) {
        simWidth = maxW;
        simHeight = maxW / targetAR;
    } else {
        simHeight = maxH;
        simWidth = maxH * targetAR;
    }

    // Morph CSS styles of simulator
    simulator.style.width = `${simWidth}px`;
    simulator.style.height = `${simHeight}px`;
    simulator.querySelector('.canvas-resolution-badge').innerText = `${targetWidth} x ${targetHeight} px`;

    // Recalculate dynamic scales
    scaleX = simWidth / targetWidth;
    scaleY = simHeight / targetHeight;

    // Refresh simulation coords
    updateSimulatorFromInputs();
}

resolutionPreset.addEventListener('change', adjustSimulatorAspect);
resWidth.addEventListener('input', adjustSimulatorAspect);
resHeight.addEventListener('input', adjustSimulatorAspect);

// ==========================================
// 2. Interactive Canvas Selection Logic
// ==========================================

let isDragging = false;
let isResizing = false;
let activeHandle = null;
let startX, startY, startLeft, startTop, startWidth, startHeight;

function updateSimulatorFromInputs() {
    const x = Math.max(0, parseInt(inputX.value) || 0);
    const y = Math.max(0, parseInt(inputY.value) || 0);
    const w = Math.max(10, parseInt(inputW.value) || 10);
    const h = Math.max(10, parseInt(inputH.value) || 10);

    // Apply scale factors
    const simX = Math.min(simWidth, x * scaleX);
    const simY = Math.min(simHeight, y * scaleY);
    const simW = Math.min(simWidth - simX, w * scaleX);
    const simH = Math.min(simHeight - simY, h * scaleY);

    cropBox.style.left = `${simX}px`;
    cropBox.style.top = `${simY}px`;
    cropBox.style.width = `${simW}px`;
    cropBox.style.height = `${simH}px`;
}

function updateInputsFromSimulator() {
    const left = parseFloat(cropBox.style.left) || 0;
    const top = parseFloat(cropBox.style.top) || 0;
    const width = parseFloat(cropBox.style.width) || 0;
    const height = parseFloat(cropBox.style.height) || 0;

    // Convert back to absolute pixels
    inputX.value = Math.round(left / scaleX);
    inputY.value = Math.round(top / scaleY);
    inputW.value = Math.round(width / scaleX);
    inputH.value = Math.round(height / scaleY);
}

// Drag & Drop event bindings
cropBox.addEventListener('mousedown', (e) => {
    if (e.target.classList.contains('resize-handle')) {
        isResizing = true;
        activeHandle = e.target;
        startWidth = cropBox.offsetWidth;
        startHeight = cropBox.offsetHeight;
        startLeft = cropBox.offsetLeft;
        startTop = cropBox.offsetTop;
        startX = e.clientX;
        startY = e.clientY;
        e.preventDefault();
        return;
    }

    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    startLeft = cropBox.offsetLeft;
    startTop = cropBox.offsetTop;
    e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
    if (isDragging || isResizing) {
        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;

        if (isDragging) {
            let newLeft = startLeft + deltaX;
            let newTop = startTop + deltaY;

            newLeft = Math.max(0, Math.min(simWidth - cropBox.offsetWidth, newLeft));
            newTop = Math.max(0, Math.min(simHeight - cropBox.offsetHeight, newTop));

            cropBox.style.left = `${newLeft}px`;
            cropBox.style.top = `${newTop}px`;
            updateInputsFromSimulator();
        }

        if (isResizing) {
            if (activeHandle.classList.contains('se')) {
                let newWidth = startWidth + deltaX;
                let newHeight = startHeight + deltaY;

                newWidth = Math.max(20, Math.min(simWidth - startLeft, newWidth));
                newHeight = Math.max(20, Math.min(simHeight - startTop, newHeight));

                cropBox.style.width = `${newWidth}px`;
                cropBox.style.height = `${newHeight}px`;
            } else if (activeHandle.classList.contains('sw')) {
                let newWidth = startWidth - deltaX;
                let newHeight = startHeight + deltaY;
                let newLeft = startLeft + deltaX;

                if (newLeft >= 0 && newWidth >= 20) {
                    cropBox.style.left = `${newLeft}px`;
                    cropBox.style.width = `${newWidth}px`;
                }
                newHeight = Math.max(20, Math.min(simHeight - startTop, newHeight));
                cropBox.style.height = `${newHeight}px`;
            } else if (activeHandle.classList.contains('ne')) {
                let newWidth = startWidth + deltaX;
                let newHeight = startHeight - deltaY;
                let newTop = startTop + deltaY;

                newWidth = Math.max(20, Math.min(simWidth - startLeft, newWidth));
                cropBox.style.width = `${newWidth}px`;
                if (newTop >= 0 && newHeight >= 20) {
                    cropBox.style.top = `${newTop}px`;
                    cropBox.style.height = `${newHeight}px`;
                }
            } else if (activeHandle.classList.contains('nw')) {
                let newWidth = startWidth - deltaX;
                let newHeight = startHeight - deltaY;
                let newLeft = startLeft + deltaX;
                let newTop = startTop + deltaY;

                if (newLeft >= 0 && newWidth >= 20) {
                    cropBox.style.left = `${newLeft}px`;
                    cropBox.style.width = `${newWidth}px`;
                }
                if (newTop >= 0 && newHeight >= 20) {
                    cropBox.style.top = `${newTop}px`;
                    cropBox.style.height = `${newHeight}px`;
                }
            }
            updateInputsFromSimulator();
        }
    }

    if (isSrcDragging || isSrcResizing) {
        const deltaX = e.clientX - startSrcX;
        const deltaY = e.clientY - startSrcY;

        if (isSrcDragging) {
            let newLeft = startSrcLeft + deltaX;
            let newTop = startSrcTop + deltaY;

            newLeft = Math.max(0, Math.min(sourceSimWidth - sourceCropBox.offsetWidth, newLeft));
            newTop = Math.max(0, Math.min(sourceSimHeight - sourceCropBox.offsetHeight, newTop));

            sourceCropBox.style.left = `${newLeft}px`;
            sourceCropBox.style.top = `${newTop}px`;
            updateSrcInputsFromSimulator();
        }

        if (isSrcResizing) {
            if (activeSrcHandle.classList.contains('se')) {
                let newWidth = startSrcWidth + deltaX;
                let newHeight = startSrcHeight + deltaY;

                newWidth = Math.max(20, Math.min(sourceSimWidth - startSrcLeft, newWidth));
                newHeight = Math.max(20, Math.min(sourceSimHeight - startSrcTop, newHeight));

                sourceCropBox.style.width = `${newWidth}px`;
                sourceCropBox.style.height = `${newHeight}px`;
            } else if (activeSrcHandle.classList.contains('sw')) {
                let newWidth = startSrcWidth - deltaX;
                let newHeight = startSrcHeight + deltaY;
                let newLeft = startSrcLeft + deltaX;

                if (newLeft >= 0 && newWidth >= 20) {
                    sourceCropBox.style.left = `${newLeft}px`;
                    sourceCropBox.style.width = `${newWidth}px`;
                }
                newHeight = Math.max(20, Math.min(sourceSimHeight - startSrcTop, newHeight));
                sourceCropBox.style.height = `${newHeight}px`;
            } else if (activeSrcHandle.classList.contains('ne')) {
                let newWidth = startSrcWidth + deltaX;
                let newHeight = startSrcHeight - deltaY;
                let newTop = startSrcTop + deltaY;

                newWidth = Math.max(20, Math.min(sourceSimWidth - startSrcLeft, newWidth));
                sourceCropBox.style.width = `${newWidth}px`;
                if (newTop >= 0 && newHeight >= 20) {
                    sourceCropBox.style.top = `${newTop}px`;
                    sourceCropBox.style.height = `${newHeight}px`;
                }
            } else if (activeSrcHandle.classList.contains('nw')) {
                let newWidth = startSrcWidth - deltaX;
                let newHeight = startSrcHeight - deltaY;
                let newLeft = startSrcLeft + deltaX;
                let newTop = startSrcTop + deltaY;

                if (newLeft >= 0 && newWidth >= 20) {
                    sourceCropBox.style.left = `${newLeft}px`;
                    sourceCropBox.style.width = `${newWidth}px`;
                }
                if (newTop >= 0 && newHeight >= 20) {
                    sourceCropBox.style.top = `${newTop}px`;
                    sourceCropBox.style.height = `${newHeight}px`;
                }
            }
            updateSrcInputsFromSimulator();
        }
    }
});

document.addEventListener('mouseup', () => {
    isDragging = false;
    isResizing = false;
    activeHandle = null;

    isSrcDragging = false;
    isSrcResizing = false;
    activeSrcHandle = null;
});

[inputX, inputY, inputW, inputH].forEach(input => {
    input.addEventListener('input', updateSimulatorFromInputs);
    input.addEventListener('change', updateSimulatorFromInputs);
});

// Interactive Template & Layer Overlay Preview
function resolveTemplateUrl(val) {
    if (!val) return '';
    val = val.trim();
    if (val.startsWith('http://') || val.startsWith('https://')) {
        return val;
    }
    if (val === 'sample_template.png') {
        return '/templates/sample_template.png';
    }
    // Convert server path to web URL
    let normalized = val.replace(/\\/g, '/');
    if (normalized.includes('storage/')) {
        let idx = normalized.indexOf('storage/');
        return '/' + normalized.substring(idx);
    }
    if (normalized.includes('templates/')) {
        let idx = normalized.indexOf('templates/');
        return '/' + normalized.substring(idx);
    }
    return '/templates/' + val;
}

function updateTemplatePreview() {
    const templateId = templateIdInput.value;
    const url = resolveTemplateUrl(templateId);
    
    if (url) {
        templatePreviewOverlay.style.backgroundImage = `url('${url}')`;
    } else {
        templatePreviewOverlay.style.backgroundImage = 'none';
    }

    const layoutMode = document.getElementById('layout-mode').value;
    if (layoutMode === 'TEMPLATE_ON_TOP') {
        templatePreviewOverlay.style.zIndex = '3';
        cropBox.style.zIndex = '2';
    } else {
        templatePreviewOverlay.style.zIndex = '1';
        cropBox.style.zIndex = '3';
    }
}

// Listeners for live template updates
templateIdInput.addEventListener('input', updateTemplatePreview);
templateIdInput.addEventListener('change', updateTemplatePreview);
document.getElementById('layout-mode').addEventListener('change', updateTemplatePreview);

// ==========================================
// 2B. Source Video Crop Selection Logic
// ==========================================

let isSrcDragging = false;
let isSrcResizing = false;
let activeSrcHandle = null;
let startSrcX, startSrcY, startSrcLeft, startSrcTop, startSrcWidth, startSrcHeight;
let sourceScaleX = 1.0;
let sourceScaleY = 1.0;
let sourceSimWidth = 480;
let sourceSimHeight = 270;

// Toggle visibility of source crop section
enableSourceCrop.addEventListener('change', () => {
    if (enableSourceCrop.checked) {
        sourceCropSection.style.display = 'flex';
        // Auto-load preview if there is a path in video-sources
        const sources = videoSourcesInput.value.split('\n').map(s => s.trim()).filter(s => s.length > 0);
        if (sources.length > 0 && !sourceVideoPreview.src) {
            let firstSource = sources[0];
            if (firstSource === 'sample_video.mp4' || firstSource.endsWith('sample_video.mp4')) {
                loadSourceVideoPreview('/storage/temp/sample_video.mp4');
            } else if (firstSource.startsWith('storage/')) {
                loadSourceVideoPreview('/' + firstSource);
            } else {
                loadSourceVideoPreview(firstSource);
            }
        }
    } else {
        sourceCropSection.style.display = 'none';
    }
});

function loadSourceVideoPreview(url) {
    if (!url) return;
    sourceVideoPreview.src = url;
    sourceVideoPreview.load();
    sourceVideoPreview.play().catch(e => console.log("Video auto-play blocked:", e));
}

// Adjust source simulator size and scale factors based on metadata
sourceVideoPreview.addEventListener('loadedmetadata', () => {
    let sourceVideoWidth = sourceVideoPreview.videoWidth || 640;
    let sourceVideoHeight = sourceVideoPreview.videoHeight || 360;
    
    const maxW = 480;
    const maxH = 270;
    const sourceAR = sourceVideoWidth / sourceVideoHeight;
    const maxAR = maxW / maxH;
    
    if (sourceAR > maxAR) {
        sourceSimWidth = maxW;
        sourceSimHeight = maxW / sourceAR;
    } else {
        sourceSimHeight = maxH;
        sourceSimWidth = maxH * sourceAR;
    }
    
    sourceSimulator.style.width = `${sourceSimWidth}px`;
    sourceSimulator.style.height = `${sourceSimHeight}px`;
    
    sourceScaleX = sourceSimWidth / sourceVideoWidth;
    sourceScaleY = sourceSimHeight / sourceVideoHeight;
    
    // Check if the currently active video item already has a crop configured
    if (activeVideoItem && activeVideoItem.crop) {
        inputSrcX.value = activeVideoItem.crop.x;
        inputSrcY.value = activeVideoItem.crop.y;
        inputSrcW.value = activeVideoItem.crop.width;
        inputSrcH.value = activeVideoItem.crop.height;
    } else {
        // Set default coordinates to full video cover
        inputSrcX.value = 0;
        inputSrcY.value = 0;
        inputSrcW.value = sourceVideoWidth;
        inputSrcH.value = sourceVideoHeight;
    }
    
    updateSrcSimulatorFromInputs();
});

function updateSrcSimulatorFromInputs() {
    const x = Math.max(0, parseInt(inputSrcX.value) || 0);
    const y = Math.max(0, parseInt(inputSrcY.value) || 0);
    const w = Math.max(10, parseInt(inputSrcW.value) || 10);
    const h = Math.max(10, parseInt(inputSrcH.value) || 10);
    
    const simX = Math.min(sourceSimWidth, x * sourceScaleX);
    const simY = Math.min(sourceSimHeight, y * sourceScaleY);
    const simW = Math.min(sourceSimWidth - simX, w * sourceScaleX);
    const simH = Math.min(sourceSimHeight - simY, h * sourceScaleY);
    
    sourceCropBox.style.left = `${simX}px`;
    sourceCropBox.style.top = `${simY}px`;
    sourceCropBox.style.width = `${simW}px`;
    sourceCropBox.style.height = `${simH}px`;
}

function updateSrcInputsFromSimulator() {
    const left = parseFloat(sourceCropBox.style.left) || 0;
    const top = parseFloat(sourceCropBox.style.top) || 0;
    const width = parseFloat(sourceCropBox.style.width) || 0;
    const height = parseFloat(sourceCropBox.style.height) || 0;
    
    inputSrcX.value = Math.round(left / sourceScaleX);
    inputSrcY.value = Math.round(top / sourceScaleY);
    inputSrcW.value = Math.round(width / sourceScaleX);
    inputSrcH.value = Math.round(height / sourceScaleY);
}

// Drag & Resize Mouse bindings for Source Video Crop
sourceCropBox.addEventListener('mousedown', (e) => {
    if (e.target.classList.contains('resize-handle')) {
        isSrcResizing = true;
        activeSrcHandle = e.target;
        startSrcWidth = sourceCropBox.offsetWidth;
        startSrcHeight = sourceCropBox.offsetHeight;
        startSrcLeft = sourceCropBox.offsetLeft;
        startSrcTop = sourceCropBox.offsetTop;
        startSrcX = e.clientX;
        startSrcY = e.clientY;
        e.preventDefault();
        return;
    }
    
    isSrcDragging = true;
    startSrcX = e.clientX;
    startSrcY = e.clientY;
    startSrcLeft = sourceCropBox.offsetLeft;
    startSrcTop = sourceCropBox.offsetTop;
    e.preventDefault();
});

[inputSrcX, inputSrcY, inputSrcW, inputSrcH].forEach(input => {
    input.addEventListener('input', updateSrcSimulatorFromInputs);
    input.addEventListener('change', updateSrcSimulatorFromInputs);
});


// ==========================================
// 3. Local Drag-and-Drop Upload Logic
// ==========================================

// Template Upload Actions
btnUploadTemplate.addEventListener('click', () => templateUploadInput.click());
templateUploadInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        uploadTemplate(file);
    }
});

function uploadTemplate(file) {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);

    templateUploadProgress.style.display = 'block';
    templateUploadProgress.innerText = `Uploading template: 0%`;

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            templateUploadProgress.innerText = `Uploading template: ${pct}%`;
        }
    });

    xhr.addEventListener('load', () => {
        if (xhr.status === 201) {
            const data = JSON.parse(xhr.responseText);
            showToast(`Template uploaded successfully!`, 'success');
            templateIdInput.value = data.temp_path;
            updateTemplatePreview();
            templateUploadProgress.innerText = `Uploaded: ${file.name}`;
            setTimeout(() => {
                templateUploadProgress.style.display = 'none';
            }, 3000);
        } else {
            const err = JSON.parse(xhr.responseText || '{}');
            showToast(`Template upload failed: ${err.detail || xhr.statusText}`, 'error');
            templateUploadProgress.style.display = 'none';
        }
    });

    xhr.addEventListener('error', () => {
        showToast('Network error during template upload.', 'error');
        templateUploadProgress.style.display = 'none';
    });

    xhr.open('POST', '/api/v1/render/upload');
    xhr.send(formData);
}

// Video Drag-and-Drop Actions
dropzone.addEventListener('click', () => uploadInput.click());

uploadInput.addEventListener('change', (e) => {
    handleUploadedFiles(e.target.files);
});

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
});

dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    handleUploadedFiles(e.dataTransfer.files);
});

function handleUploadedFiles(files) {
    Array.from(files).forEach(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        const supported = ['mp4', 'mov', 'avi', 'mkv', 'png', 'jpg', 'jpeg'];
        
        if (supported.includes(ext)) {
            uploadFileStream(file);
        } else {
            showToast(`Format .${ext} is not supported for rendering.`, 'error');
        }
    });
}

function uploadFileStream(file) {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);

    const rowId = 'upload-' + Math.random().toString(36).substring(2, 9);
    const row = document.createElement('div');
    row.className = 'upload-progress-item';
    row.id = rowId;
    row.innerHTML = `
        <span class="upload-progress-name" title="${file.name}">${file.name}</span>
        <div class="upload-progress-right">
            <div class="upload-progress-bar">
                <div class="upload-progress-fill" style="width: 0%"></div>
            </div>
            <span class="upload-progress-pct">0%</span>
        </div>
    `;
    progressList.appendChild(row);

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            row.querySelector('.upload-progress-fill').style.width = `${pct}%`;
            row.querySelector('.upload-progress-pct').innerText = `${pct}%`;
        }
    });

    xhr.addEventListener('load', () => {
        if (xhr.status === 201) {
            const data = JSON.parse(xhr.responseText);
            showToast(`Uploaded ${file.name} successfully!`, 'success');
            
            // Append file temporary path on a new line in textarea
            let currentVal = videoSourcesInput.value.trim();
            if (currentVal.length > 0) {
                currentVal += '\n' + data.temp_path;
            } else {
                currentVal = data.temp_path;
            }
            videoSourcesInput.value = currentVal;
            
            // Sync the textarea state to update the carousel UI immediately
            syncStateFromTextarea();
            
            // Automatically select the newly uploaded video in the carousel and preview it
            const newItem = videoSourcesData.find(item => item.source === data.temp_path);
            if (newItem) {
                selectVideoItem(newItem);
            } else {
                loadSourceVideoPreview(data.url);
            }
            
            setTimeout(() => {
                row.style.opacity = '0';
                row.style.transition = 'opacity 0.5s';
                setTimeout(() => row.remove(), 500);
            }, 1500);
        } else {
            const err = JSON.parse(xhr.responseText || '{}');
            showToast(`Upload failed: ${err.detail || xhr.statusText}`, 'error');
            row.remove();
        }
    });

    xhr.addEventListener('error', () => {
        showToast('Network error occurred during file upload.', 'error');
        row.remove();
    });

    xhr.open('POST', '/api/v1/render/upload');
    xhr.send(formData);
}

// ==========================================
// 4. Local Mock Loader
// ==========================================

btnLoadTest.addEventListener('click', () => {
    document.getElementById('template-id').value = 'sample_template.png';
    document.getElementById('video-sources').value = 'storage/temp/sample_video.mp4';
    document.getElementById('layout-mode').value = 'TEMPLATE_ON_TOP';
    
    // Switch to vertical layout test (9:16)
    resolutionPreset.value = '9:16';
    adjustSimulatorAspect();
    
    // Set crop area values
    inputX.value = '140';
    inputY.value = '460';
    inputW.value = '800';
    inputH.value = '1000';
    
    updateSimulatorFromInputs();
    updateTemplatePreview();
    
    // Sync the textarea state to populate the carousel
    syncStateFromTextarea();
    
    // Select the test video item
    if (videoSourcesData.length > 0) {
        selectVideoItem(videoSourcesData[0]);
    }
    
    showToast('Test vertical assets loaded! Click Dispatch to process.', 'success');
});

// ==========================================
// 4B. Interactive Per-Video Crop state & Carousel
// ==========================================

let videoSourcesData = [];
let activeVideoItem = null;

const carouselGroup = document.getElementById('carousel-group');
const uploadedVideosCarousel = document.getElementById('uploaded-videos-carousel');

function syncStateFromTextarea() {
    const lines = videoSourcesInput.value.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    
    // Keep items that are still in the textarea
    videoSourcesData = videoSourcesData.filter(item => lines.includes(item.source));
    
    // Add new items from textarea
    lines.forEach(line => {
        const exists = videoSourcesData.some(item => item.source === line);
        if (!exists) {
            let url = line;
            let normalized = line.replace(/\\/g, '/');
            if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
                url = line;
            } else if (normalized.includes('storage/')) {
                let idx = normalized.indexOf('storage/');
                url = '/' + normalized.substring(idx);
            } else if (normalized.includes('templates/')) {
                let idx = normalized.indexOf('templates/');
                url = '/' + normalized.substring(idx);
            } else if (normalized.startsWith('storage/')) {
                url = '/' + line;
            } else if (normalized.startsWith('/storage/')) {
                url = line;
            } else {
                url = '/storage/temp/' + line;
            }
            videoSourcesData.push({
                source: line,
                url: url,
                crop: null
            });
        }
    });
    
    // If our active item was removed, reset it
    if (activeVideoItem && !videoSourcesData.includes(activeVideoItem)) {
        activeVideoItem = null;
    }
    
    updateCarouselUI();
}

function updateCarouselUI() {
    if (videoSourcesData.length > 0) {
        carouselGroup.style.display = 'flex';
    } else {
        carouselGroup.style.display = 'none';
        activeVideoItem = null;
        return;
    }

    uploadedVideosCarousel.innerHTML = '';
    videoSourcesData.forEach((item, index) => {
        const filename = item.source.split('/').pop().split('\\').pop();
        const itemCard = document.createElement('div');
        itemCard.className = `carousel-item-card ${activeVideoItem === item ? 'active' : ''}`;
        if (item.crop) {
            itemCard.classList.add('has-crop');
        }
        
        // Dynamic styles for premium look
        itemCard.style.cssText = `
            flex: 0 0 auto;
            padding: 8px 12px;
            background: ${activeVideoItem === item ? 'rgba(168, 85, 247, 0.15)' : 'rgba(255, 255, 255, 0.02)'};
            border: 1px solid ${activeVideoItem === item ? 'var(--primary)' : 'var(--border-color)'};
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            gap: 4px;
            min-width: 90px;
            max-width: 140px;
            text-align: center;
            transition: all 0.2s ease-in-out;
            box-shadow: ${activeVideoItem === item ? '0 0 8px rgba(168, 85, 247, 0.3)' : 'none'};
        `;
        
        itemCard.innerHTML = `
            <span style="font-size: 11px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; color: var(--text-color);" title="${filename}">${filename}</span>
            <span style="font-size: 9px; color: ${item.crop ? 'var(--success)' : 'var(--text-muted)'}; font-weight: 700;">
                ${item.crop ? '✂️ Custom' : 'Default Center'}
            </span>
        `;

        itemCard.addEventListener('click', () => {
            selectVideoItem(item);
        });

        uploadedVideosCarousel.appendChild(itemCard);
    });
}

function selectVideoItem(item) {
    activeVideoItem = item;
    updateCarouselUI();

    // Check "Crop Input Video" checkbox to show crop area
    enableSourceCrop.checked = true;
    sourceCropSection.style.display = 'flex';

    // Load preview
    loadSourceVideoPreview(item.url);

    // If this item already has a crop, apply it to numeric inputs and crop box UI
    if (item.crop) {
        inputSrcX.value = item.crop.x;
        inputSrcY.value = item.crop.y;
        inputSrcW.value = item.crop.width;
        inputSrcH.value = item.crop.height;
        updateSrcSimulatorFromInputs();
    }
}

function saveActiveVideoCrop() {
    if (activeVideoItem && enableSourceCrop.checked) {
        activeVideoItem.crop = {
            x: parseInt(inputSrcX.value) || 0,
            y: parseInt(inputSrcY.value) || 0,
            width: parseInt(inputSrcW.value) || 100,
            height: parseInt(inputSrcH.value) || 100
        };
        updateCarouselUI();
    }
}

// Hook into inputs and drag events to save crop coordinates
[inputSrcX, inputSrcY, inputSrcW, inputSrcH].forEach(input => {
    input.addEventListener('change', saveActiveVideoCrop);
    input.addEventListener('input', saveActiveVideoCrop);
});

sourceCropBox.addEventListener('mouseup', saveActiveVideoCrop);
document.addEventListener('mousemove', () => {
    if (isSrcDragging || isSrcResizing) {
        saveActiveVideoCrop();
    }
});

// Event listeners to sync manual text inputs / uploaded files
videoSourcesInput.addEventListener('input', syncStateFromTextarea);
videoSourcesInput.addEventListener('change', syncStateFromTextarea);

// ==========================================
// 5. API Submissions & Polling
// ==========================================

renderForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const templateId = document.getElementById('template-id').value.trim();
    const layout = document.getElementById('layout-mode').value;
    
    // Ensure state is fully synced from textarea
    syncStateFromTextarea();

    if (videoSourcesData.length === 0) {
        showToast('Please add at least one source video.', 'error');
        return;
    }

    const payload = {
        template_id: templateId,
        crop_coordinates: {
            x: parseInt(inputX.value),
            y: parseInt(inputY.value),
            width: parseInt(inputW.value),
            height: parseInt(inputH.value)
        },
        layout: layout,
        // Send as VideoSourceItem list: [{ source: string, crop: CropCoordinates | null }]
        video_sources: videoSourcesData.map(item => ({
            source: item.source,
            crop: enableSourceCrop.checked ? item.crop : null
        })),
        output_width: targetWidth,
        output_height: targetHeight,
        smart_crop: document.getElementById('enable-smart-crop').checked
    };

    // Fallback: If "Crop Input Video" is checked globally but a video item does not have a custom crop yet,
    // we assign the current source crop coordinates from inputs as its crop coordinates.
    if (enableSourceCrop.checked) {
        const fallbackCrop = {
            x: parseInt(inputSrcX.value),
            y: parseInt(inputSrcY.value),
            width: parseInt(inputSrcW.value),
            height: parseInt(inputSrcH.value)
        };
        // Fill crop coordinates for items that don't have custom ones yet
        payload.video_sources.forEach(item => {
            if (!item.crop) {
                item.crop = fallbackCrop;
            }
        });
    }

    const btnSubmit = document.getElementById('btn-submit');
    btnSubmit.disabled = true;
    btnSubmit.innerText = 'Dispatching Batch...';

    try {
        const response = await fetch('/api/v1/render/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Failed to submit batch');
        }

        const data = await response.json();
        showToast(`Batch queued successfully! ID: ${data.batch_id.slice(0, 8)}`, 'success');
        
        saveBatchToHistory(data.batch_id);
        renderBatchCard(data.batch_id);
        startPolling(data.batch_id);

    } catch (err) {
        console.error(err);
        showToast(err.message, 'error');
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerText = '🚀 Dispatch Render Batch';
    }
});

// Toast Notifications System
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Local Storage History Management
function getBatchHistory() {
    try {
        const history = JSON.parse(localStorage.getItem('rendering_batches') || '[]');
        return Array.isArray(history) ? history.filter(id => typeof id === 'string') : [];
    } catch (e) {
        console.error("Error parsing batch history from localStorage:", e);
        return [];
    }
}

function saveBatchToHistory(batchId) {
    const history = getBatchHistory();
    if (!history.includes(batchId)) {
        history.unshift(batchId);
        localStorage.setItem('rendering_batches', JSON.stringify(history));
    }
}

function removeBatchFromHistory(batchId) {
    let history = getBatchHistory();
    history = history.filter(id => id !== batchId);
    localStorage.setItem('rendering_batches', JSON.stringify(history));
}

btnClearHistory.addEventListener('click', () => {
    const history = getBatchHistory();
    history.forEach(batchId => {
        if (activePollings[batchId]) {
            clearInterval(activePollings[batchId]);
            delete activePollings[batchId];
        }
    });
    localStorage.setItem('rendering_batches', '[]');
    document.querySelectorAll('.batch-card').forEach(card => card.remove());
    emptyState.style.display = 'flex';
    showToast('Batch history cleared.', 'info');
});


// ==========================================
// 6. Batch Cards Rendering & Updates
// ==========================================

function renderBatchCard(batchId) {
    if (!batchId || typeof batchId !== 'string') return;
    emptyState.style.display = 'none';

    const existing = document.getElementById(`batch-card-${batchId}`);
    if (existing) existing.remove();

    const card = document.createElement('div');
    card.id = `batch-card-${batchId}`;
    card.className = 'batch-card pending';
    card.innerHTML = `
        <div class="batch-card-header">
            <div class="batch-meta">
                <h4>Batch Rendering <span class="batch-id-short">(${batchId.slice(0, 8)})</span></h4>
                <p style="font-size: 11px; color: var(--text-muted);">Template: Loading...</p>
                <p class="batch-res-info" style="font-size: 10px; color: var(--primary); font-weight: 700; margin-top: 2px;">Resolution: Loading...</p>
            </div>
            <div class="header-badges" style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
                <span class="batch-badge pending">PENDING</span>
                <div class="zip-download-container" style="display: none;"></div>
            </div>
        </div>
        
        <div class="progress-container">
            <div class="progress-header">
                <span>Rendering Progress</span>
                <span class="progress-percent">0%</span>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: 0%"></div>
            </div>
        </div>

        <div class="batch-stats-summary">
            <span class="stat-total">Total: 0</span>
            <span class="stat-completed" style="color: var(--success);">Completed: 0</span>
            <span class="stat-failed" style="color: var(--danger);">Failed: 0</span>
        </div>

        <button class="btn-toggle-tasks" type="button">
            <span>▼ View individual tasks</span>
        </button>

        <div class="tasks-details-panel" id="tasks-panel-${batchId}">
            <!-- Task rows -->
        </div>
    `;

    card.querySelector('.btn-toggle-tasks').addEventListener('click', (e) => {
        const panel = document.getElementById(`tasks-panel-${batchId}`);
        const btnText = e.currentTarget.querySelector('span');
        if (panel.style.display === 'flex') {
            panel.style.display = 'none';
            btnText.innerText = '▼ View individual tasks';
        } else {
            panel.style.display = 'flex';
            btnText.innerText = '▲ Hide individual tasks';
        }
    });

    batchesList.insertBefore(card, batchesList.firstChild);
}

function updateBatchCardUI(batchId, data) {
    const card = document.getElementById(`batch-card-${batchId}`);
    if (!card) return;

    card.className = `batch-card ${data.status.toLowerCase()}`;
    
    const badge = card.querySelector('.batch-badge');
    badge.innerText = data.status;
    badge.className = `batch-badge ${data.status.toLowerCase()}`;

    card.querySelector('.batch-meta p').innerText = `Template: ${data.template_id}`;
    
    const resW = data.output_width || 'Auto';
    const resH = data.output_height || 'Auto';
    card.querySelector('.batch-res-info').innerText = `Canvas Resolution: ${resW} x ${resH} px`;

    // Render Zip Download link if batch is complete and contains rendered items
    const zipContainer = card.querySelector('.zip-download-container');
    if (data.status === 'COMPLETED' && data.completed_tasks > 0) {
        zipContainer.style.display = 'block';
        zipContainer.innerHTML = `
            <a href="/api/v1/render/download/batch/${batchId}" class="btn-download-zip" download>
                📥 Download ZIP
            </a>
        `;
    } else {
        zipContainer.style.display = 'none';
        zipContainer.innerHTML = '';
    }

    card.querySelector('.progress-percent').innerText = `${data.progress}%`;
    const progressFill = card.querySelector('.progress-bar-fill');
    progressFill.style.width = `${data.progress}%`;
    
    if (data.status === 'PROCESSING') {
        progressFill.classList.add('rendering');
    } else {
        progressFill.classList.remove('rendering');
    }

    card.querySelector('.stat-total').innerText = `Total: ${data.total_tasks}`;
    card.querySelector('.stat-completed').innerText = `Completed: ${data.completed_tasks}`;
    card.querySelector('.stat-failed').innerText = `Failed: ${data.failed_tasks}`;

    const tasksPanel = document.getElementById(`tasks-panel-${batchId}`);
    tasksPanel.innerHTML = '';

    data.tasks.forEach(task => {
        const taskRow = document.createElement('div');
        taskRow.className = 'task-row';
        
        let actionsHtml = '';
        if (task.status === 'COMPLETED' && task.output_path) {
            const webUrl = `/storage/${batchId}/${task.task_id}.mp4`;
            actionsHtml = `
                <button class="btn-play-video" title="Play Rendered Video" onclick="playVideo('${batchId}', '${task.task_id}', '${task.source}')">
                    ▶
                </button>
                <a href="${webUrl}" download="video_${task.task_id}.mp4" class="btn-download-video" title="Download video file">
                    📥
                </a>
            `;
        } else if (task.status === 'FAILED') {
            const safeError = encodeURIComponent(task.error || 'Unknown error');
            actionsHtml = `
                <button class="btn-error-info" title="View Error details" onclick="showErrorDetails(decodeURIComponent('${safeError}'))">
                    ⚠
                </button>
            `;
        }

        const sourceLabel = task.source.split('/').pop().split('\\').pop();

        taskRow.innerHTML = `
            <div class="task-info-left">
                <span class="task-source-name" title="${task.source}">${sourceLabel}</span>
                <span class="task-status-text ${task.status.toLowerCase()}">${task.status}</span>
            </div>
            <div class="task-actions-right">
                <span class="task-pct">${task.progress.toFixed(0)}%</span>
                ${actionsHtml}
            </div>
        `;
        tasksPanel.appendChild(taskRow);
    });
}


// ==========================================
// 7. Polling Engine
// ==========================================

function startPolling(batchId) {
    if (activePollings[batchId]) return;

    const poll = async () => {
        try {
            const response = await fetch(`/api/v1/render/status/${batchId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    clearInterval(activePollings[batchId]);
                    delete activePollings[batchId];
                    removeBatchFromHistory(batchId);
                    const card = document.getElementById(`batch-card-${batchId}`);
                    if (card) card.remove();
                    return;
                }
                throw new Error('API error polling status');
            }

            const data = await response.json();
            updateBatchCardUI(batchId, data);

            const isFinished = (data.status === 'COMPLETED' || data.status === 'FAILED');
            if (isFinished) {
                clearInterval(activePollings[batchId]);
                delete activePollings[batchId];
                showToast(`Batch ${batchId.slice(0, 8)} rendering workflow completed!`, 'success');
            }

        } catch (err) {
            console.warn(`Polling error for batch ${batchId}:`, err);
        }
    };

    poll();
    activePollings[batchId] = setInterval(poll, 1000);
}


// ==========================================
// 8. Playback & Error Dialogs
// ==========================================

window.playVideo = function(batchId, taskId, originalSource) {
    const webUrl = `/storage/${batchId}/${taskId}.mp4`;
    modalVideoPlayer.src = webUrl;
    modalVideoTitle.innerText = `Render: ${originalSource.split('/').pop().split('\\').pop()}`;
    modalVideoPath.innerText = `Source url/path: ${originalSource}`;
    videoModal.classList.add('active');
};

window.showErrorDetails = function(errorMsg) {
    alert(`Render Task Error details:\n\n${errorMsg}`);
};

modalClose.addEventListener('click', () => {
    videoModal.classList.remove('active');
    modalVideoPlayer.pause();
    modalVideoPlayer.src = '';
});

window.addEventListener('click', (e) => {
    if (e.target === videoModal) {
        videoModal.classList.remove('active');
        modalVideoPlayer.pause();
        modalVideoPlayer.src = '';
    }
});


// ==========================================
// 9. App Initialization
// ==========================================

function init() {
    adjustSimulatorAspect();
    updateTemplatePreview();
    syncStateFromTextarea();
    
    const history = getBatchHistory();
    if (history.length > 0) {
        emptyState.style.display = 'none';
        history.forEach(batchId => {
            renderBatchCard(batchId);
            startPolling(batchId);
        });
    }
}

// Start application
init();
