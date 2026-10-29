"""Synthetic contract mutations, not browser/native acceptance evidence."""
import copy, unittest
import verify_results as v

def fixture(arm='candidate', mode='showAll', dpr=2, css=(0,0,375,602), prior=None):
    viewport=[css[2]*dpr,css[3]*dpr]
    scale=min(css[2]/320,css[3]/240) if mode=='showAll' else 1
    left=(css[2]-320*scale)/2;top=(css[3]-240*scale)/2
    points=[[round(left+x*320*scale),round(top+y*240*scale)] for x,y in [( .15,.15),(.85,.15),(.15,.85),(.85,.85),(.5,.5)]]
    drag=[points[-1],[points[-1][0]+8,points[-1][1]+6]]
    before={'epoch':1,'measurement':{'css':list(css),'dpr':dpr,'events':[]},'traces':[]}
    previous=(0,0)
    if prior:
        before=copy.deepcopy(prior['after']);before['measurement']['css']=list(css)
        e=before['measurement']['events'][-1]
        previous=v.stage_position([e['offsetX'],e['offsetY']],[n*dpr for n in e['rect'][2:]],dpr,mode)
    after=copy.deepcopy(before)
    def emit(label,*fields):after['traces'].append('DENSITY|'+label+'|'+'|'.join(map(str,fields)))
    for i,(a,b) in enumerate([(p,p) for p in points]+[drag]):
        events=[]
        for typ,p in [('pointerdown',a),('pointerup',b)]:
            e={'type':typ,'trusted':True,'pointerType':'touch','id':i,'x':p[0]+css[0],'y':p[1]+css[1],
               'offsetX':p[0],'offsetY':p[1],'rect':list(css),'lastMove':None}
            events.append(e)
        if i==5:
            move={**events[1],'type':'pointermove'};move.pop('lastMove');events[1]['lastMove']=move
        after['measurement']['events']+=events
        down=v.current_position(a,viewport,dpr,mode) if arm=='candidate' else v.reported_position(previous,viewport,dpr,mode)
        up=v.current_position(b,viewport,dpr,mode)
        stage=[320,240] if mode=='showAll' else list(css[2:])
        hit=str(100<=down[0]<=220 and 70<=down[1]<=170).lower()
        raw_down=v.stage_position(a,viewport,dpr,mode) if arm=='candidate' else previous
        raw_up=v.stage_position(b,viewport,dpr,mode)
        target=[100+(raw_up[0]-raw_down[0])/20,70+(raw_up[1]-raw_down[1])/20] if hit=='true' else [100,70]
        emit('DOWN',*down,hit,*stage,mode,'');emit('UP',*up,*target,*stage,mode,'')
        emit('MOTION',3 if i==5 else 0,*up,*target);emit('RESET',100,70)
        previous=v.stage_position(b,viewport,dpr,mode)
    return {'arm':arm,'scaleMode':mode,'before':before,'after':after,'points':points,'drag':drag}

class InputContracts(unittest.TestCase):
    def test_all_modes_dpr_arms_and_resize(self):
        for arm in ('candidate','baseline'):
            for mode in ('showAll','noScale'):
                for dpr in (2,3):
                    first=fixture(arm,mode,dpr);v.check_inputs(first)
                    v.check_inputs(fixture(arm,mode,dpr,(0,0,667,310),first))
    def test_baseline_post_resize_negative_target_is_not_erased(self):
        for mode in ('showAll','noScale'):
            r=fixture('baseline',mode,2,(0,0,667,310),fixture('baseline',mode))
            first=v.trace(r['after'],'UP')[-6]
            self.assertLess(float(first[2]),100)
            v.check_inputs(r)
            # A fabricated reset target in the pre-reset UP must fail even when
            # matching MOTION is tampered too, leaving order/counts intact.
            lines=r['after']['traces'];start=len(r['before']['traces'])
            for offset,indices in [(1,(4,5)),(2,(5,6))]:
                parts=lines[start+offset].split('|')
                parts[indices[0]],parts[indices[1]]='100','70'
                lines[start+offset]='|'.join(parts)
            with self.assertRaisesRegex(AssertionError,'target delta'):v.check_inputs(r)
    def test_candidate_rejects_old_down(self):
        r=fixture('baseline');r['arm']='candidate'
        with self.assertRaisesRegex(AssertionError,'DOWN'):v.check_inputs(r)
    def test_baseline_is_explicit_negative_not_candidate_gold(self):
        r=fixture();r['arm']='baseline'
        with self.assertRaisesRegex(AssertionError,'DOWN'):v.check_inputs(r)
    def test_release_different_from_last_move_requires_current_candidate_point(self):
        def earlier_move(r):
            move=r['after']['measurement']['events'][-1]['lastMove']
            for key in ('offsetX','offsetY','x','y'):move[key]-=2
        r=fixture();earlier_move(r);v.check_inputs(r)
        b=fixture('baseline');earlier_move(b)
        with self.assertRaisesRegex(AssertionError,'UP'):v.check_inputs(b)
        # A candidate stale release response cannot be excused as old-baseline behavior.
        r=fixture();lines=r['after']['traces'];up=lines[-3].split('|');up[2]=str(float(up[2])-2)
        lines[-3]='|'.join(up)
        with self.assertRaises(AssertionError):v.check_inputs(r)
    def test_mutations_fail_closed(self):
        for kind in ('offset','rect','pointer','untrusted','missing','reset','motion','order','up','move','target'):
            r=fixture();events=r['after']['measurement']['events'];lines=r['after']['traces']
            if kind=='offset':events[0]['offsetX']+=1
            if kind=='rect':events[0]['rect'][0]+=1
            if kind=='pointer':events[1]['id']=999
            if kind=='untrusted':events[0]['trusted']=False
            if kind=='missing':events.pop()
            if kind=='reset':lines[-1]='DENSITY|RESET|101|70'
            if kind=='motion':lines[-2]=lines[-2].replace('MOTION|3|','MOTION|0|')
            if kind=='order':lines[-1],lines[-2]=lines[-2],lines[-1]
            if kind=='up':lines[1]=lines[1].replace('UP|','UP|999|',1)
            if kind=='move':events[-1]['lastMove']['trusted']=False
            if kind=='target':
                parts=lines[-3].split('|');parts[4]='999';lines[-3]='|'.join(parts)
            with self.subTest(kind=kind),self.assertRaises((AssertionError,ValueError)):v.check_inputs(r)
if __name__=='__main__':unittest.main(verbosity=2)
