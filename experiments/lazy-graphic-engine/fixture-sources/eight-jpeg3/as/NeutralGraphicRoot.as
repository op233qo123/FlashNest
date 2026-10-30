package {
 import flash.display.MovieClip;
 import flash.events.Event;
 import flash.events.KeyboardEvent;
 public class NeutralGraphicRoot extends MovieClip {
  private var shown:Boolean=false;
  public function NeutralGraphicRoot() {
   if(stage)start();else addEventListener(Event.ADDED_TO_STAGE,start);
  }
  private function start(e:Event=null):void {
   removeEventListener(Event.ADDED_TO_STAGE,start);stop();
   graphics.beginFill(0x204060);graphics.drawRect(0,0,24,24);graphics.endFill();
   stage.addEventListener(KeyboardEvent.KEY_DOWN,key);
   trace("NEUTRAL_GRAPHIC ready unshown=8");
  }
  private function key(e:KeyboardEvent):void {
   if(e.keyCode!=32 || shown)return;shown=true;
   stage.removeEventListener(KeyboardEvent.KEY_DOWN,key);
   gotoAndStop(2);trace("NEUTRAL_GRAPHIC first-display requested=1 remaining-unshown=7");
  }
 }
}
