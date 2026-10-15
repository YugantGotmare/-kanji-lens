/* Local OCR sends only the crop to our Python server; browser OCR is optional. */
(() => {
  let image = null, worker = null, busy = false, generation = 0, loading = null, upload = null;
  const canvas = $('preview'), context = canvas.getContext('2d');
  const status = text => $('scan-status').textContent = text;
  const controls = ['crop-left', 'crop-top', 'crop-width', 'crop-height'];
  function rectangle() {
    const [left, top, width, height] = controls.map(id => Number($(id).value) / 100);
    return {x: Math.floor(left * image.width), y: Math.floor(top * image.height),
      w: Math.max(1, Math.floor(Math.min(width, 1 - left) * image.width)),
      h: Math.max(1, Math.floor(Math.min(height, 1 - top) * image.height))};
  }
  function preview() {
    if (!image) return;
    canvas.width = image.width; canvas.height = image.height;
    context.drawImage(image, 0, 0);
    const r = rectangle();
    context.fillStyle = 'rgba(0,0,0,.45)';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, r.x, r.y, r.w, r.h, r.x, r.y, r.w, r.h);
    context.strokeStyle = '#e9ba53'; context.lineWidth = Math.max(3, canvas.width / 300);
    context.strokeRect(r.x, r.y, r.w, r.h);
  }
  function setBusy(value) {
    busy = value;
    ['scan', 'rotate', 'layout', 'ocr-engine', 'photo', 'camera', ...controls].forEach(id => $(id).disabled = value);
    $('cancel-scan').hidden = !value; $('scan-progress').hidden = !value;
  }
  function cancel(message) {
    ++generation; const current = worker; worker = null;
    upload?.abort(); upload = null;
    if (current) current.terminate().catch(() => {});
    setBusy(false); status(message);
  }
  async function select(event) {
    const file = event.target.files[0]; event.target.value = '';
    if (!file || busy) return;
    const ticket = ++generation;
    if (!file.type.startsWith('image/') || file.size > 20 * 1024 * 1024) {
      status('Choose an image smaller than 20 MB.'); return;
    }
    const url = URL.createObjectURL(file);
    try {
      const picture = new Image(); picture.src = url; await picture.decode();
      if (ticket !== generation) return;
      if (!picture.naturalWidth || !picture.naturalHeight) throw new Error('Empty image');
      const scale = Math.min(1, 2400 / Math.max(picture.naturalWidth, picture.naturalHeight));
      image = document.createElement('canvas');
      image.width = Math.round(picture.naturalWidth * scale); image.height = Math.round(picture.naturalHeight * scale);
      image.getContext('2d').drawImage(picture, 0, 0, image.width, image.height);
      controls.forEach((id, i) => $(id).value = i < 2 ? 0 : 100);
      $('image-tools').hidden = false; $('recognized').hidden = true;
      preview(); status('Adjust the crop, then read the image.');
    } catch { status('This image could not be opened. Try a JPEG, PNG, or WebP image.'); }
    finally { URL.revokeObjectURL(url); }
  }
  function loadEngine() {
    if (window.Tesseract) return Promise.resolve();
    if (!loading) loading = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/tesseract.js@6.0.1/dist/tesseract.min.js';
      const timer = setTimeout(() => { script.remove(); loading = null; reject(new Error('OCR download timed out. Check your connection and try again.')); }, 45000);
      script.onload = () => { clearTimeout(timer); resolve(); };
      script.onerror = () => { clearTimeout(timer); script.remove(); loading = null; reject(new Error('Could not download the OCR engine. Check your connection and try again.')); };
      document.head.append(script);
    });
    return loading;
  }
  function choices() {
    $('kanji-choices').replaceChildren(...Study.kanji($('recognized-text').value).map(ch => {
      const button = node('button', ch, 'kanji-choice'); button.type = 'button';
      button.onclick = () => { $('query').value = ch; $('search').requestSubmit(); };
      return button;
    }));
  }
  async function localScan(ticket) {
    const r = rectangle(), crop = document.createElement('canvas');
    crop.width = r.w; crop.height = r.h;
    const ctx = crop.getContext('2d'); ctx.fillStyle = 'white'; ctx.fillRect(0, 0, r.w, r.h);
    ctx.drawImage(image, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h);
    const blob = await new Promise(resolve => crop.toBlob(resolve, 'image/png'));
    if (ticket !== generation) return;
    if (!blob) throw new Error('Could not prepare this photo. Try another image.');
    status('Recognizing on your local server. The first scan loads the model and may take longer…');
    $('scan-progress').removeAttribute('value');
    upload = new AbortController();
    const response = await fetch(`/api/ocr?layout=${encodeURIComponent($('layout').value)}`, {
      method: 'POST', headers: {'Content-Type': 'image/png'}, body: blob, signal: upload.signal
    });
    const result = await response.json();
    if (ticket !== generation) return;
    if (!response.ok) throw new Error(result.error || 'Local recognition failed.');
    $('recognized-text').value = result.text;
    $('recognized').hidden = false; choices();
    for (const alternative of result.alternatives || []) {
      const button = node('button', `Alternative: ${alternative.text}`); button.type = 'button';
      button.onclick = () => { $('recognized-text').value = alternative.text; choices(); };
      $('ocr-alternatives').append(button);
    }
    status(!Study.kanji(result.text).length ? 'No kanji found. Try a closer crop, single-character layout, or correct the text.' :
      result.uncertain ? 'Local OCR is uncertain or its attempts disagree. Check the image and candidates before choosing.' : 'Local OCR finished. Check the text, then tap a kanji to see its words.');
  }
  $('photo').onchange = select; $('camera').onchange = select;
  controls.forEach(id => $(id).oninput = preview);
  $('rotate').onclick = () => {
    if (!image || busy) return;
    const rotated = document.createElement('canvas'); rotated.width = image.height; rotated.height = image.width;
    const c = rotated.getContext('2d'); c.translate(rotated.width, 0); c.rotate(Math.PI / 2); c.drawImage(image, 0, 0);
    image = rotated; preview();
  };
  $('scan').onclick = async () => {
    if (!image || busy) return;
    const ticket = ++generation; setBusy(true); $('recognized').hidden = true;
    $('ocr-alternatives').replaceChildren();
    const timer = setTimeout(() => {
      if (ticket === generation) cancel('Recognition timed out. Try a smaller crop and check your connection.');
    }, 120000);
    $('scan-progress').value = 0; status('Loading Japanese recognition. The first scan may take a minute…');
    try {
      if ($('ocr-engine').value === 'local') { await localScan(ticket); return; }
      await loadEngine(); if (ticket !== generation) return;
      const language = $('layout').value === '5' ? 'jpn_vert' : 'jpn';
      const created = await Tesseract.createWorker(language, 1, {logger: message => {
        if (ticket !== generation) return;
        if (message.status === 'recognizing text') {
          $('scan-progress').value = message.progress;
          status(`Reading image… ${Math.round(message.progress * 100)}%`);
        }
      }});
      if (ticket !== generation) { await created.terminate(); return; }
      worker = created;
      const r = rectangle(), input = document.createElement('canvas');
      const scale = Math.min(3, Math.max(1, 1200 / Math.max(r.w, r.h)));
      // Tight glyph crops need a margin; flatten transparency onto white first.
      const padding = Math.max(24, Math.round(Math.max(r.w, r.h) * scale * .08));
      input.width = Math.round(r.w * scale) + padding * 2; input.height = Math.round(r.h * scale) + padding * 2;
      const c = input.getContext('2d'); c.fillStyle = 'white'; c.fillRect(0, 0, input.width, input.height);
      c.drawImage(image, r.x, r.y, r.w, r.h, padding, padding, input.width - padding * 2, input.height - padding * 2);
      const layout = $('layout').value;
      const mode = layout === 'auto' ? '6' : layout === 'line' ? '7' : layout;
      await created.setParameters({tessedit_pageseg_mode: mode});
      if (ticket !== generation) return;
      let result = await created.recognize(input);
      if (ticket !== generation) return;
      if ((!Study.kanji(result.data.text).length || result.data.confidence < 35) && layout !== '5') {
        status('Trying a cleaner background and single-character recognition…');
        // Remove pale checkerboard patterns often baked into downloaded glyphs.
        // Keep the original photo intact; this is a second OCR attempt only.
        const pixels = c.getImageData(0, 0, input.width, input.height);
        for (let i = 0; i < pixels.data.length; i += 4) {
          const gray = .299 * pixels.data[i] + .587 * pixels.data[i + 1] + .114 * pixels.data[i + 2];
          const value = gray < 160 ? 0 : 255;
          pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = value;
        }
        c.putImageData(pixels, 0, 0);
        await created.setParameters({tessedit_pageseg_mode: layout === 'auto' ? '10' : mode});
        if (ticket !== generation) return;
        const retry = await created.recognize(input);
        if (ticket !== generation) return;
        if ((Study.kanji(retry.data.text).length && (!Study.kanji(result.data.text).length || retry.data.confidence > result.data.confidence)) || !result.data.text.trim()) result = retry;
        if (!Study.kanji(result.data.text).length || result.data.confidence < 35) {
          // Raw-line mode avoids the segmentation heuristics that can split a
          // large kanji into separate kana-shaped components.
          status('Trying an alternative layout for the cropped character…');
          await created.setParameters({tessedit_pageseg_mode: '13'});
          if (ticket !== generation) return;
          const alternative = await created.recognize(input);
          if (ticket !== generation) return;
          if (Study.kanji(alternative.data.text).length && (!Study.kanji(result.data.text).length || alternative.data.confidence > result.data.confidence)) result = alternative;
        }
      }
      if (ticket !== generation) return;
      $('recognized-text').value = result.data.text.trim().slice(0, 2000);
      $('recognized').hidden = false; choices();
      status(Study.kanji(result.data.text).length ? (result.data.confidence < 50 ? 'Recognition is uncertain. Check or correct the text before choosing a kanji.' : 'Check the text, then tap a kanji to see its words.') : 'No kanji found. Try a closer crop, rotate the image, or correct the text below.');
    } catch (error) { if (ticket === generation) status(error.message || 'Recognition failed. Try a clearer image.'); }
    finally {
      clearTimeout(timer);
      if (ticket === generation) {
        const current = worker; worker = null;
        upload = null;
        setBusy(false);
        if (current) await current.terminate().catch(() => {});
      }
    }
  };
  $('cancel-scan').onclick = () => cancel('Scan cancelled.');
  $('recognized-text').oninput = choices;
  $('use-recognized').onclick = () => {
    $('query').value = $('recognized-text').value.slice(0, 200); $('search').requestSubmit();
  };
})();
