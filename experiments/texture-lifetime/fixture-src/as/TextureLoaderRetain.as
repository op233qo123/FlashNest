package {
 import flash.display.Sprite;
 import flash.display.Loader;
 import flash.display.DisplayObject;
 import flash.display.StageScaleMode;
 import flash.display.StageAlign;
 import flash.net.URLRequest;
 import flash.events.Event;
 import flash.events.IOErrorEvent;
 import flash.events.KeyboardEvent;
 public class TextureLoaderRetain extends Sprite {
  private var loader:Loader;
  private var kept:Array=[];
  private var cycle:int=0;
  private var frames:int=0;
  private var phase:String="idle";
  public function TextureLoaderRetain(){if(stage)start();else addEventListener(Event.ADDED_TO_STAGE,start);}
  private function start(e:Event=null):void {
   removeEventListener(Event.ADDED_TO_STAGE,start);stage.scaleMode=StageScaleMode.NO_SCALE;stage.align=StageAlign.TOP_LEFT;
   stage.addEventListener(KeyboardEvent.KEY_DOWN,key);addEventListener(Event.ENTER_FRAME,tick);
   trace("TEXTURE_LIFETIME loader-retain ready");
  }
  private function key(e:KeyboardEvent):void {
   if(e.keyCode==83 && phase=="idle"){loadNext();}
   else if(e.keyCode==82 && phase=="complete"){
    for(var i:int=0;i<kept.length;i++){var child:DisplayObject=kept[i];addChild(child);child.x=32+i*72;child.y=32;trace("TEXTURE_LIFETIME loader-retain ping="+Object(child).ping());}
    phase="retained";trace("TEXTURE_LIFETIME loader-retain retained="+kept.length);
   } else if(e.keyCode==85 && (phase=="retained" || phase=="complete")){
    for(var j:int=0;j<kept.length;j++){var old:DisplayObject=kept[j];if(old.parent==this)removeChild(old);}
    old=null;kept=[];frames=0;phase="dropping";trace("TEXTURE_LIFETIME loader-retain dropped");
   }
  }
  private function loadNext():void {
   cycle++;loader=new Loader();loader.contentLoaderInfo.addEventListener(Event.COMPLETE,loaded);
   loader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR,failed);
   addChild(loader);loader.x=32;loader.y=32;phase="loading";
   loader.load(new URLRequest("texture-child.swf?cycle="+cycle));
  }
  private function loaded(e:Event):void {phase="showing";frames=0;trace("TEXTURE_LIFETIME loader-retain loaded="+cycle);}
  private function failed(e:IOErrorEvent):void {trace("TEXTURE_LIFETIME loader-retain error="+e.text);phase="error";}
  private function tick(e:Event):void {
   frames++;
   if(phase=="showing" && frames>=8){
    if(true && cycle<=3)kept.push(loader.content);
    loader.contentLoaderInfo.removeEventListener(Event.COMPLETE,loaded);loader.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR,failed);
    loader.unload();removeChild(loader);loader=null;phase="unloaded";frames=0;trace("TEXTURE_LIFETIME loader-retain unloaded="+cycle);
   } else if(phase=="unloaded" && frames>=8){if(cycle<6)loadNext();else{phase="complete";trace("TEXTURE_LIFETIME loader-retain complete");}}
   else if(phase=="dropping" && frames==120){phase="done";trace("TEXTURE_LIFETIME loader-retain done");}
  }
 }
}
