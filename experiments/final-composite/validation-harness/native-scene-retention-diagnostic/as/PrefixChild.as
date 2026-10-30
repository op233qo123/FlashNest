package {
 import flash.display.Sprite;
 import flash.events.Event;
 public class PrefixChild extends Sprite {
  public function PrefixChild() { addEventListener(Event.ENTER_FRAME,first); }
  private function first(e:Event):void {
   removeEventListener(Event.ENTER_FRAME,first);
   dispatchEvent(new Event("sceneFirstFrame",true));
  }
 }
}
