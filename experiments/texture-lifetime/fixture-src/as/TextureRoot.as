package {
 import flash.display.MovieClip;
 import flash.display.StageScaleMode;
 import flash.display.StageAlign;
 import flash.events.Event;
 import flash.events.KeyboardEvent;
 public class TextureRoot extends MovieClip {
  private var cycling:Boolean=false;
  private var wait:int=0;
  private var item:int=0;
  private var cycle:int=0;
  private var count:int;
  public function TextureRoot() { if(stage)start();else addEventListener(Event.ADDED_TO_STAGE,start); }
  private function start(e:Event=null):void {
   removeEventListener(Event.ADDED_TO_STAGE,start);stop();count=totalFrames-1;
   stage.scaleMode=StageScaleMode.NO_SCALE;stage.align=StageAlign.TOP_LEFT;
   stage.addEventListener(KeyboardEvent.KEY_DOWN,key);addEventListener(Event.ENTER_FRAME,tick);
   trace("TEXTURE_LIFETIME root-"+count+" ready");
  }
  private function key(e:KeyboardEvent):void {
   if(cycling)return;
   if(e.keyCode==83 || e.keyCode==82) {cycling=true;item=1;cycle++;gotoAndStop(2);wait=4;}
   else if(e.keyCode==85) {gotoAndStop(1);trace("TEXTURE_LIFETIME root-"+count+" empty");}
  }
  private function tick(e:Event):void {
   if(!cycling || --wait>0)return;
   trace("TEXTURE_LIFETIME root-"+count+" settled resource="+item+" cycle="+cycle);
   if(item==count){cycling=false;trace("TEXTURE_LIFETIME root-"+count+" cycle="+cycle);return;}
   item++;gotoAndStop(item+1);wait=4;
  }
 }
}
