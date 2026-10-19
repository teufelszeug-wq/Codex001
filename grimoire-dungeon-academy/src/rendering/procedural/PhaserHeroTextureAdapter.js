export class PhaserHeroTextureAdapter {
  constructor(scene) { this.scene = scene; }

  upload(key, surface) {
    if (this.scene.textures.exists(key)) this.scene.textures.remove(key);
    const texture = this.scene.textures.createCanvas(key, surface.width, surface.height);
    const ctx = texture.getContext();
    const image = ctx.createImageData(surface.width, surface.height);
    for (let i = 0; i < surface.pixels.length; i++) {
      const c = surface.pixels[i] >>> 0, o = i * 4;
      image.data[o]=(c>>>16)&0xff; image.data[o+1]=(c>>>8)&0xff; image.data[o+2]=c&0xff; image.data[o+3]=(c>>>24)&0xff;
    }
    ctx.imageSmoothingEnabled = false;
    ctx.putImageData(image,0,0); texture.refresh(); return key;
  }

  uploadAtlas(key, frames, frameWidth = 96, frameHeight = 96) {
    if (!frames?.length) throw new Error('frames required');
    const width = frameWidth * frames.length;
    if (this.scene.textures.exists(key)) this.scene.textures.remove(key);
    const texture = this.scene.textures.createCanvas(key,width,frameHeight);
    const ctx = texture.getContext(); ctx.imageSmoothingEnabled=false;
    for(let f=0; f<frames.length; f++){
      const surface=frames[f], image=ctx.createImageData(frameWidth,frameHeight);
      for(let i=0;i<surface.pixels.length;i++){
        const c=surface.pixels[i]>>>0,o=i*4; image.data[o]=(c>>>16)&255;image.data[o+1]=(c>>>8)&255;image.data[o+2]=c&255;image.data[o+3]=(c>>>24)&255;
      }
      ctx.putImageData(image,f*frameWidth,0); texture.add(String(f),0,f*frameWidth,0,frameWidth,frameHeight);
    }
    texture.refresh(); return key;
  }
}
