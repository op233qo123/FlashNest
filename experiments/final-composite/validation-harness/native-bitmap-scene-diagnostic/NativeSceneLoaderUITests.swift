import XCTest
import UIKit
import CryptoKit

final class NativeSceneLoaderUITests: XCTestCase {
    private var identity: [String: Any] = [:]
    override func setUpWithError() throws {
        continueAfterFailure = true;executionTimeAllowance = 180
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "SamplingIdentity",withExtension: "json"))
        identity = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        XCTAssertEqual(identity["arm"] as? String,"candidate");XCUIDevice.shared.orientation = .portrait
    }
    private func emit(_ value: [String: Any],name: String,marker: String) throws {
        let data = try JSONSerialization.data(withJSONObject: value,options: [.sortedKeys])
        guard data.count <= 65536 else { throw NSError(domain:"BoundedEvidence",code:1) }
        let attachment = XCTAttachment(data:data,uniformTypeIdentifier:"public.json")
        attachment.name=name;attachment.lifetime = .keepAlways;add(attachment)
        print(marker+" "+String(decoding:data,as:UTF8.self))
    }
    private func snapshot(_ app: XCUIApplication) -> [String: Any] {
        let element=app.staticTexts["scene-evidence"];var last:[String:Any]=[:]
        guard element.exists else { return ["observationError":"Native evidence label missing"] }
        if let text=element.value as? String,let data=text.data(using:.utf8),let v=try? JSONSerialization.jsonObject(with:data) as? [String:Any] { last=v }
        let previous=last["request"] as? Int ?? -1;let button=app.buttons["scene-snapshot"]
        if button.exists && button.isHittable { button.tap() }
        let deadline=ProcessInfo.processInfo.systemUptime+2
        repeat {
            if let text=element.value as? String,let data=text.data(using:.utf8),let v=try? JSONSerialization.jsonObject(with:data) as? [String:Any] { last=v }
            if let request=last["request"] as? Int,request>previous,last["jsCompletedForRequest"] as? Int==request { break }
            Thread.sleep(forTimeInterval:0.1)
        } while ProcessInfo.processInfo.systemUptime<deadline
        return last
    }
    private func phases(_ s:[String:Any])->[String] { (s["asRecords"] as? [[String:Any]] ?? []).compactMap{($0["phase"] as? [String:Any])?["phase"] as? String} }
    private func drawCount(_ s:[String:Any])->Int {
        let m=s["measurement"] as? [String:Any] ?? [:],calls=m["renderCalls"] as? [String:Int] ?? [:]
        return ["drawArrays","drawElements","drawArraysInstanced","drawElementsInstanced"].reduce(0){$0+(calls[$1] ?? 0)}
    }
    func testSizedBitmapSceneTransition() throws {
        let app=XCUIApplication();app.launchArguments=["-FlashNest.language","en","-AppleLanguages","(en)","-AppleLocale","en_US","--scene-case","sized-bitmap"]
        let launchedAt=ProcessInfo.processInfo.systemUptime;app.launch();defer{app.terminate()}
        var last:[String:Any]=[:],readyAt:Double?=nil,error="",count=0,oldDraw=0,transitionSent=false
        var visuals:[[String:Any]]=[]
        func capture(_ s:[String:Any]) throws {
            guard count<32 else{return};count+=1
            try emit(["schema":"flashnest-native-scene-observation-v1","diagnosticOnly":true,"nativeAcceptance":false,"case":"sized-bitmap","index":count,"nativeUptimeSeconds":ProcessInfo.processInfo.systemUptime,"identity":identity,"snapshot":s],name:"bitmap-scene-\(count)",marker:"FLASHNEST_SCENE_OBSERVATION_JSON")
        }
        let play=app.webViews.buttons["Play / enable audio"].firstMatch
        if play.waitForExistence(timeout:30) && play.isEnabled && play.isHittable { play.tap() } else { error="Original Play unavailable" }
        if error.isEmpty {
            repeat {
                last=snapshot(app)
                if last["ready"] as? Bool==true {readyAt=ProcessInfo.processInfo.systemUptime;break}
                if last["terminated"] as? Bool==true || !(last["failure"] as? String ?? "").isEmpty {error="Native failure before ready";break}
                Thread.sleep(forTimeInterval:0.25)
            } while ProcessInfo.processInfo.systemUptime<launchedAt+50
            if readyAt==nil && error.isEmpty {error="Initial50s ready deadline"}
        } else {last=snapshot(app)}
        try capture(last)
        if let readyAt {
            let deadline=readyAt+120
            while count<31 && ProcessInfo.processInfo.systemUptime<deadline && error.isEmpty {
                if last["terminated"] as? Bool==true || !(last["failure"] as? String ?? "").isEmpty {error="Native failure during transition";break}
                if !transitionSent && phases(last).contains("old.awaiting-space") && drawCount(last)>0 {
                    do {
                        let visual=try bitmapScreenshot(before:last,label:"old");visuals.append(visual)
                        try emit(visual,name:"bitmap-old-visual",marker:"FLASHNEST_BITMAP_VISUAL_JSON")
                        guard visual["paletteMatches"] as? Bool==true else {error="Old bitmap not visibly correct; transition not sent";break}
                        guard ProcessInfo.processInfo.systemUptime<deadline else {error="Old visual reached120s deadline";break}
                        oldDraw=drawCount(last)
                        let trigger=app.buttons["scene-transition"]
                        guard trigger.exists && trigger.isEnabled && trigger.isHittable else {error="Single transition control unavailable";break}
                        trigger.tap();transitionSent=true // Exactly one attempt, original session.key Space down/up.
                    } catch let captureError { error="Old visual capture failed: \(captureError)";break }
                }
                if transitionSent && phases(last).contains("parent.done") && drawCount(last)>oldDraw {
                    do {
                        let visual=try bitmapScreenshot(before:last,label:"new");visuals.append(visual)
                        try emit(visual,name:"bitmap-new-visual",marker:"FLASHNEST_BITMAP_VISUAL_JSON")
                        if visual["paletteMatches"] as? Bool != true {error="New bitmap not visibly correct"}
                    } catch let captureError {error="New visual capture failed: \(captureError)"}
                    break
                }
                let remaining=deadline-ProcessInfo.processInfo.systemUptime;if remaining<=0{break}
                Thread.sleep(forTimeInterval:min(4,remaining));last=snapshot(app);try capture(last)
            }
        }
        let activeFinishedAt=ProcessInfo.processInfo.systemUptime
        let complete=error.isEmpty && visuals.count==2 && transitionSent && phases(last).contains("parent.done") && (readyAt.map{activeFinishedAt<=$0+120} ?? false)
        if !complete && error.isEmpty {error="Bitmap transition not completed within120s/32 records"}
        last=snapshot(app);try capture(last)
        let raw=XCTAttachment(screenshot:XCUIScreen.main.screenshot());raw.name="bitmap-final-screen";raw.lifetime = .keepAlways;add(raw)
        let finishedAt=ProcessInfo.processInfo.systemUptime
        if finishedAt-activeFinishedAt>10 && error.isEmpty {error="Final evidence exceeded10s"}
        try emit(["schema":"flashnest-native-scene-case-v1","diagnosticOnly":true,"nativeAcceptance":false,"case":"sized-bitmap","identity":identity,"launchedAt":launchedAt,"readyAt":readyAt.map{$0 as Any} ?? NSNull(),"activeFinishedAt":activeFinishedAt,"finishedAt":finishedAt,"finalEvidenceBudgetSeconds":10,"observationCount":count,"parentDoneObserved":complete,"terminated":last["terminated"] as? Bool ?? false,"error":error,"lastSnapshot":last,"transitionAttempted":transitionSent,"visualCount":visuals.count],name:"bitmap-scene-outcome",marker:"FLASHNEST_SCENE_CASE_JSON")
        XCTAssertTrue(error.isEmpty,error);XCTAssertTrue(complete);XCTAssertEqual(last["transitionCount"] as? Int,1)
        XCTAssertTrue(last["sameWK"] as? Bool ?? false);XCTAssertEqual(last["epoch"] as? Int,1)
        XCTAssertFalse(last["asOverflow"] as? Bool ?? true);XCTAssertFalse(last["traceSuppressed"] as? Bool ?? true)
    }
    private func bitmapScreenshot(before:[String:Any],label:String) throws -> [String:Any] {
        let name="bitmap-"+label,image=XCUIScreen.main.screenshot().image,raw=try XCTUnwrap(image.cgImage)
        let rawBytes=try XCTUnwrap(UIImage(cgImage:raw).pngData())
        let rawHash=SHA256.hash(data:rawBytes).map{String(format:"%02x",$0)}.joined()
        let rawAttachment=XCTAttachment(data:rawBytes,uniformTypeIdentifier:"public.png");rawAttachment.name=name+"-raw-full";rawAttachment.lifetime = .keepAlways;add(rawAttachment)
        let swaps:Bool
        switch image.imageOrientation {case .left,.right,.leftMirrored,.rightMirrored:swaps=true;default:swaps=false}
        let width=swaps ? raw.height:raw.width,height=swaps ? raw.width:raw.height
        let format=UIGraphicsImageRendererFormat();format.scale=1;format.opaque=true;format.preferredRange = .standard
        let normalized=UIGraphicsImageRenderer(size:CGSize(width:CGFloat(width),height:CGFloat(height)),format:format).image{_ in image.draw(in:CGRect(x:0,y:0,width:CGFloat(width),height:CGFloat(height)))}
        let cg=try XCTUnwrap(normalized.cgImage)
        let normalizedBytes=try XCTUnwrap(normalized.pngData())
        let normalizedHash=SHA256.hash(data:normalizedBytes).map{String(format:"%02x",$0)}.joined()
        let normalizedAttachment=XCTAttachment(data:normalizedBytes,uniformTypeIdentifier:"public.png");normalizedAttachment.name=name+"-normalized-full";normalizedAttachment.lifetime = .keepAlways;add(normalizedAttachment)
        let viewport=try XCTUnwrap(before["viewport"] as? [Double]),screen=try XCTUnwrap(before["screenBounds"] as? [Double]),dpr=try XCTUnwrap(before["screenScale"] as? Double)
        let measurement=try XCTUnwrap(before["measurement"] as? [String:Any]),css=try XCTUnwrap(measurement["css"] as? [Double])
        guard dpr==2,screen.count==2,viewport.count==4,css.count==4,css[2]>=288,css[3]>=288,
              abs(Double(cg.width)-screen[0]*dpr)<=1,abs(Double(cg.height)-screen[1]*dpr)<=1 else {throw NSError(domain:"IndependentScreenshotGeometry",code:1)}
        let rect=CGRect(x:(viewport[0]+css[0])*dpr,y:(viewport[1]+css[1])*dpr,width:css[2]*dpr,height:css[3]*dpr).integral
        guard rect.minX>=0,rect.minY>=0,rect.maxX<=CGFloat(cg.width),rect.maxY<=CGFloat(cg.height) else {throw NSError(domain:"ScreenshotClip",code:2)}
        let crop=try XCTUnwrap(cg.cropping(to:rect))
        guard crop.width==Int(rect.width),crop.height==Int(rect.height) else {throw NSError(domain:"ScreenshotClip",code:3)}
        let bytes=try XCTUnwrap(UIImage(cgImage:crop).pngData()),hash=SHA256.hash(data:bytes).map{String(format:"%02x",$0)}.joined()
        let attachment=XCTAttachment(data:bytes,uniformTypeIdentifier:"public.png");attachment.name=name+"-canvas.png";attachment.lifetime = .keepAlways;add(attachment)
        let expected:[[Int]]=label=="old" ? [[255,0,0],[0,255,0],[0,0,255],[255,255,255]]:[[0,255,255],[255,0,255],[255,255,0],[0,0,0]]
        let centers=[[96,96],[224,96],[96,224],[224,224]];var samples:[[String:Any]]=[];var matches=true
        for (index,center) in centers.enumerated() {
            let x=Int(floor(Double(center[0])*dpr+(viewport[0]+css[0])*dpr-Double(rect.minX)+0.5))
            let y=Int(floor(Double(center[1])*dpr+(viewport[1]+css[1])*dpr-Double(rect.minY)+0.5))
            let patch=try XCTUnwrap(crop.cropping(to:CGRect(x:CGFloat(x-2),y:CGFloat(y-2),width:5,height:5)))
            guard patch.width==5,patch.height==5 else {throw NSError(domain:"PixelPatchClip",code:4)}
            var rgba=[UInt8](repeating:0,count:5*5*4)
            let ok=rgba.withUnsafeMutableBytes{buffer -> Bool in
                guard let context=CGContext(data:buffer.baseAddress,width:5,height:5,bitsPerComponent:8,bytesPerRow:20,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue|CGBitmapInfo.byteOrder32Big.rawValue) else{return false}
                context.draw(patch,in:CGRect(x:0,y:0,width:5,height:5));return true
            }
            guard ok else{throw NSError(domain:"PixelDecode",code:5)}
            var minimum=[255,255,255,255],maximum=[0,0,0,0]
            for pixel in 0..<25 {for channel in 0..<4 {let value=Int(rgba[pixel*4+channel]);minimum[channel]=min(minimum[channel],value);maximum[channel]=max(maximum[channel],value)}}
            let match=(0..<3).allSatisfy{minimum[$0]>=max(0,expected[index][$0]-2) && maximum[$0]<=min(255,expected[index][$0]+2)} && minimum[3]==255
            matches=matches && match;samples.append(["centerCSS":center,"centerPixels":[x,y],"patchPixels":5,"minimumRGBA":minimum,"maximumRGBA":maximum,"matches":match])
        }
        return ["schema":"flashnest-native-bitmap-visual-v1","diagnosticOnly":true,"nativeAcceptance":false,"label":label,"identity":identity,"snapshot":before,"nativeUptimeSeconds":ProcessInfo.processInfo.systemUptime,
            "cropSHA256":hash,"paletteMatches":matches,"samples":samples,"geometry":["rawPNGSHA256":rawHash,"normalizedPNGSHA256":normalizedHash,"rawCGPixels":[raw.width,raw.height],"imageOrientation":image.imageOrientation.rawValue,"imagePointSize":[image.size.width,image.size.height],"imageScale":image.scale,"normalization":"UIImage.draw-oriented-scale1-v1","normalizedPixels":[cg.width,cg.height],"cropRectPixels":[rect.origin.x,rect.origin.y,rect.width,rect.height]] as [String:Any]]
    }
}
