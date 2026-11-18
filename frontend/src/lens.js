import { registerPlugin } from '@capacitor/core';
import { isNative } from './api.js';

export const lensUrl = 'https://lens.google.com/';
const nativeLens = registerPlugin('MindTraceLens');

export async function openLens() {
  if (!isNative) {
    window.open(lensUrl, '_blank', 'noopener');
    return { mode: 'web' };
  }
  return nativeLens.open();
}

async function toPng(blob) {
  if (blob.type === 'image/png') return blob;
  const bitmap = await createImageBitmap(blob);
  const canvas = Object.assign(document.createElement('canvas'), { width: bitmap.width, height: bitmap.height });
  canvas.getContext('2d').drawImage(bitmap, 0, 0);
  bitmap.close();
  return new Promise((resolve, reject) => canvas.toBlob(b => b ? resolve(b) : reject(new Error('Couldn’t prepare the image.')), 'image/png'));
}

export function copyImage(blobPromise) {
  if (!window.ClipboardItem || !navigator.clipboard?.write) return Promise.reject(new Error('This browser can’t copy images.'));
  return navigator.clipboard.write([new ClipboardItem({ 'image/png': Promise.resolve(blobPromise).then(toPng) })]);
}
