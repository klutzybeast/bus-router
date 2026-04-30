import React, { useState } from 'react';
import { X, ChevronRight, Clock, MapPin, AlertTriangle, CheckCircle, XCircle, Smartphone, RefreshCw } from 'lucide-react';

const sections = [
  { id: 'what', title: 'What Is This App?' },
  { id: 'login', title: 'How to Log In' },
  { id: 'attendance', title: 'Marking Attendance' },
  { id: 'absent-rule', title: 'The Absent Rule (READ THIS)' },
  { id: 'deadline', title: 'The 9:30 AM Deadline' },
  { id: 'gps', title: 'GPS Tracking' },
  { id: 'snapshot', title: 'How CamperSnapshot Sync Works' },
  { id: 'fix', title: 'Something Not Working?' },
];

export default function CounselorHelp({ onClose }) {
  const [activeSection, setActiveSection] = useState(null);

  const scrollTo = (id) => {
    setActiveSection(id);
    const el = document.getElementById(`help-${id}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div data-testid="counselor-help" style={{
      position:'fixed',top:0,left:0,right:0,bottom:0,zIndex:9999,
      background:'#111827',overflowY:'auto',WebkitOverflowScrolling:'touch'
    }}>
      {/* Header */}
      <div style={{position:'sticky',top:0,zIndex:100,background:'#1f2937',borderBottom:'1px solid #374151',padding:'12px 16px',paddingTop:'max(env(safe-area-inset-top, 12px), 40px)'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <h1 style={{margin:0,fontSize:18,fontWeight:700,color:'white'}}>Help & Training Guide</h1>
          <button data-testid="help-close-btn" onClick={onClose} style={{background:'#374151',border:'none',color:'white',width:36,height:36,borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer'}}>
            <X size={18} />
          </button>
        </div>
      </div>

      <div style={{padding:'16px',maxWidth:600,margin:'0 auto'}}>
        {/* Deadline Banner */}
        <div style={{background:'#dc2626',borderRadius:10,padding:'14px 16px',marginBottom:20,display:'flex',alignItems:'center',gap:10}}>
          <Clock size={20} color="white" />
          <div>
            <div style={{color:'white',fontSize:14,fontWeight:700}}>ALL ATTENDANCE MUST BE DONE BY 9:30 AM</div>
            <div style={{color:'#fca5a5',fontSize:12,marginTop:2}}>System locks at 9:30. No exceptions.</div>
          </div>
        </div>

        {/* Table of Contents */}
        <div style={{background:'#1f2937',borderRadius:10,padding:16,marginBottom:24,border:'1px solid #374151'}}>
          <h2 style={{color:'#9ca3af',fontSize:12,fontWeight:600,margin:'0 0 10px',letterSpacing:1}}>TABLE OF CONTENTS</h2>
          {sections.map((s, i) => (
            <button key={s.id} onClick={() => scrollTo(s.id)} data-testid={`help-toc-${s.id}`}
              style={{
                display:'flex',alignItems:'center',width:'100%',padding:'10px 8px',
                background:'transparent',border:'none',borderBottom:i < sections.length-1 ? '1px solid #374151' : 'none',
                cursor:'pointer',textAlign:'left',gap:8
              }}>
              <span style={{width:22,height:22,borderRadius:'50%',background:'#2563eb',color:'white',fontSize:11,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>{i+1}</span>
              <span style={{color:'white',fontSize:14,fontWeight:500,flex:1}}>{s.title}</span>
              <ChevronRight size={16} color="#6b7280" />
            </button>
          ))}
        </div>

        {/* Section 1: What Is This App */}
        <div id="help-what" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #2563eb',paddingLeft:12}}>1. What Is This App?</h2>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'0 0 12px'}}>
            The Bus Mapping App runs on your phone. It shows every camper assigned to your bus. As each kid boards, you mark them <strong style={{color:'#4ade80'}}>Present</strong>. If they don't show up at their stop, you mark them <strong style={{color:'#f87171'}}>Absent</strong>.
          </p>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'0 0 12px'}}>
            Your marks flow directly into <strong style={{color:'white'}}>Camper Snapshot</strong> — the central system that tracks every camper's status across camp. The front desk, supervisors, and group counselors all rely on your data being accurate and on time.
          </p>
          <div style={{background:'#1c1917',border:'1px solid #f59e0b',borderRadius:8,padding:12,marginTop:12}}>
            <div style={{color:'#f59e0b',fontSize:12,fontWeight:700,marginBottom:4}}>NON-NEGOTIABLE</div>
            <div style={{color:'#fcd34d',fontSize:13}}>You must have this app open on <strong>both</strong> the morning pickup route (marking attendance) and the afternoon drop-off (GPS tracking only). Every single day.</div>
          </div>
        </div>

        {/* Section 2: How to Log In */}
        <div id="help-login" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #2563eb',paddingLeft:12}}>2. How to Log In</h2>
          <ol style={{color:'#d1d5db',fontSize:14,lineHeight:2,margin:0,paddingLeft:20}}>
            <li>Open your browser. Go to <strong style={{color:'#60a5fa'}}>rrdcbusmapping.com/counselor</strong></li>
            <li>Type your <strong style={{color:'white'}}>bus number</strong> (e.g., 31 for Bus #31)</li>
            <li>Tap <strong style={{color:'white'}}>Go</strong></li>
            <li>Your phone will ask to share location — <strong style={{color:'#4ade80'}}>TAP ALLOW</strong></li>
            <li>You'll see your bus name, GPS status, and camper list</li>
          </ol>
          <div style={{background:'#450a0a',border:'1px solid #dc2626',borderRadius:8,padding:12,marginTop:12}}>
            <div style={{color:'#f87171',fontSize:12,fontWeight:700,marginBottom:4}}>DO NOT</div>
            <ul style={{color:'#fca5a5',fontSize:13,margin:0,paddingLeft:16,lineHeight:1.8}}>
              <li>Tap "Block" or "Don't Allow" on the location popup</li>
              <li>Type the wrong bus number — if names look wrong, log out and re-enter</li>
              <li>Share one phone between two bus counselors</li>
            </ul>
          </div>
        </div>

        {/* Section 3: Marking Attendance */}
        <div id="help-attendance" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #2563eb',paddingLeft:12}}>3. Marking Attendance</h2>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'0 0 12px'}}>
            Each camper has two buttons:
          </p>
          <div style={{display:'flex',gap:12,marginBottom:16}}>
            <div style={{flex:1,background:'#052e16',border:'1px solid #22c55e',borderRadius:8,padding:12,textAlign:'center'}}>
              <CheckCircle size={24} color="#4ade80" style={{marginBottom:4}} />
              <div style={{color:'#4ade80',fontSize:13,fontWeight:600}}>Present</div>
              <div style={{color:'#86efac',fontSize:11}}>Kid got on the bus</div>
            </div>
            <div style={{flex:1,background:'#450a0a',border:'1px solid #ef4444',borderRadius:8,padding:12,textAlign:'center'}}>
              <XCircle size={24} color="#f87171" style={{marginBottom:4}} />
              <div style={{color:'#f87171',fontSize:13,fontWeight:600}}>Absent</div>
              <div style={{color:'#fca5a5',fontSize:11}}>Kid did NOT board</div>
            </div>
          </div>
          <ol style={{color:'#d1d5db',fontSize:14,lineHeight:2,margin:0,paddingLeft:20}}>
            <li>As the bus arrives at each stop, see who is boarding</li>
            <li>Tap the <strong style={{color:'#4ade80'}}>checkmark</strong> for each camper who gets on</li>
            <li>If a camper does NOT show at their stop, tap the <strong style={{color:'#f87171'}}>X</strong></li>
            <li>Made a mistake? Just tap the other button — it switches instantly</li>
            <li>Keep going until <strong style={{color:'white'}}>Unmarked = 0</strong></li>
          </ol>
          <p style={{color:'#9ca3af',fontSize:13,marginTop:12}}>Every tap saves automatically. There is no "Submit" button.</p>
        </div>

        {/* Section 4: THE ABSENT RULE */}
        <div id="help-absent-rule" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #dc2626',paddingLeft:12}}>4. The Absent Rule (READ THIS)</h2>
          <div style={{background:'#450a0a',border:'2px solid #dc2626',borderRadius:10,padding:16,marginBottom:16}}>
            <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
              <AlertTriangle size={20} color="#f87171" />
              <span style={{color:'#f87171',fontSize:14,fontWeight:700}}>CRITICAL — DO NOT SKIP THIS</span>
            </div>
            <p style={{color:'#fca5a5',fontSize:14,lineHeight:1.7,margin:0}}>
              Even if you get a notification from the main office that a camper is absent — <strong style={{color:'white'}}>you STILL must mark them Absent in this app.</strong>
            </p>
          </div>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'0 0 12px'}}>
            <strong style={{color:'white'}}>Why?</strong> Because this app syncs directly with Camper Snapshot. If you leave a camper as "Unmarked," the system doesn't know if they're absent or if you forgot. This creates a <strong style={{color:'#f87171'}}>red conflict</strong> that the supervisor has to manually resolve.
          </p>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'0 0 12px'}}>
            The flow works like this:
          </p>
          <div style={{background:'#1f2937',borderRadius:8,padding:12,border:'1px solid #374151'}}>
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{background:'#dc2626',color:'white',padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:700,flexShrink:0}}>1</span>
                <span style={{color:'#d1d5db',fontSize:13}}>Office knows camper is absent (parent called)</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{background:'#dc2626',color:'white',padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:700,flexShrink:0}}>2</span>
                <span style={{color:'#d1d5db',fontSize:13}}>Office sends you a notification</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{background:'#dc2626',color:'white',padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:700,flexShrink:0}}>3</span>
                <span style={{color:'#f87171',fontSize:13,fontWeight:600}}>YOU still mark that camper ABSENT in this app</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{background:'#dc2626',color:'white',padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:700,flexShrink:0}}>4</span>
                <span style={{color:'#d1d5db',fontSize:13}}>System syncs — no conflict, everyone agrees</span>
              </div>
            </div>
          </div>
          <div style={{background:'#1c1917',border:'1px solid #f59e0b',borderRadius:8,padding:12,marginTop:16}}>
            <div style={{color:'#fcd34d',fontSize:13,lineHeight:1.7}}>
              <strong>Bottom line:</strong> Mark EVERY kid. Present or Absent. No exceptions. Zero Unmarked. The notification from the office does NOT replace your mark in this app.
            </div>
          </div>
        </div>

        {/* Section 5: 9:30 AM Deadline */}
        <div id="help-deadline" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #f59e0b',paddingLeft:12}}>5. The 9:30 AM Deadline</h2>
          <div style={{background:'#422006',border:'1px solid #f59e0b',borderRadius:8,padding:14}}>
            <div style={{color:'#fcd34d',fontSize:14,fontWeight:700,marginBottom:6}}>Bus attendance locks at 9:30 AM.</div>
            <p style={{color:'#fed7aa',fontSize:13,lineHeight:1.7,margin:0}}>
              After 9:30, the buttons disable and your marks won't save. You MUST complete all marking before the bus arrives at camp.
            </p>
          </div>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'16px 0 0'}}>
            At 9:30 AM, the system pulls your bus data and syncs it with Camper Snapshot and the Attendance App. If you haven't marked everyone by then, those campers show as "Unmarked" which creates conflicts the supervisor has to deal with before 9:35.
          </p>
          <p style={{color:'#9ca3af',fontSize:13,margin:'12px 0 0'}}>
            If you have an emergency and miss the deadline, contact the main office immediately. An admin can temporarily unlock attendance from the admin panel.
          </p>
        </div>

        {/* Section 6: GPS */}
        <div id="help-gps" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #22c55e',paddingLeft:12}}>6. GPS Tracking</h2>
          <div style={{display:'flex',gap:12,marginBottom:16}}>
            <div style={{flex:1,background:'#052e16',border:'1px solid #22c55e',borderRadius:8,padding:10,textAlign:'center'}}>
              <MapPin size={20} color="#4ade80" />
              <div style={{color:'#4ade80',fontSize:12,fontWeight:600,marginTop:4}}>GPS On</div>
              <div style={{color:'#86efac',fontSize:11}}>Correct state</div>
            </div>
            <div style={{flex:1,background:'#450a0a',border:'1px solid #ef4444',borderRadius:8,padding:10,textAlign:'center'}}>
              <MapPin size={20} color="#f87171" />
              <div style={{color:'#f87171',fontSize:12,fontWeight:600,marginTop:4}}>GPS Off</div>
              <div style={{color:'#fca5a5',fontSize:11}}>Fix this NOW</div>
            </div>
          </div>
          <div style={{background:'#052e16',border:'1px solid #22c55e',borderRadius:8,padding:12,marginBottom:16}}>
            <div style={{color:'#4ade80',fontSize:13,lineHeight:1.7}}>
              <strong>This app does NOT track you outside of the app.</strong> Location is ONLY active while you have the app open. Close the tab = tracking stops. It does not run in the background.
            </div>
          </div>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'0 0 12px'}}>
            <strong style={{color:'white'}}>Why GPS matters:</strong> Admin uses your location to see where all buses are on the map in real time. If a parent calls asking where Bus 31 is, admin can answer instantly. If there's an emergency, we need to know exactly where the bus is.
          </p>
          <div style={{background:'#450a0a',border:'1px solid #dc2626',borderRadius:8,padding:12,marginBottom:16}}>
            <div style={{color:'#f87171',fontSize:12,fontWeight:700,marginBottom:6}}>DO NOT EXIT THE APP UNTIL YOU REACH CAMP</div>
            <div style={{color:'#fca5a5',fontSize:13,lineHeight:1.6}}>
              Do not close the tab. Do not switch apps. Do not lock your phone. The app must stay open on your screen the entire bus ride. If you close it, GPS stops and admin loses the bus.
            </div>
          </div>
          <h3 style={{color:'white',fontSize:14,fontWeight:600,margin:'16px 0 8px'}}>How to fix GPS if you blocked it:</h3>
          <div style={{background:'#1f2937',borderRadius:8,padding:12,border:'1px solid #374151'}}>
            <div style={{color:'#d1d5db',fontSize:13,lineHeight:2}}>
              <div><strong style={{color:'white'}}>iPhone Safari:</strong> Settings &gt; Safari &gt; Location &gt; Allow</div>
              <div><strong style={{color:'white'}}>iPhone Chrome:</strong> Settings &gt; Chrome &gt; Location &gt; On</div>
              <div><strong style={{color:'white'}}>Android Chrome:</strong> Tap lock icon in URL bar &gt; Site Settings &gt; Location &gt; Allow</div>
              <div style={{marginTop:8,color:'#60a5fa'}}>Or tap the <strong>Retry</strong> button next to the red GPS badge in the app.</div>
            </div>
          </div>
        </div>

        {/* Section 7: CamperSnapshot Sync */}
        <div id="help-snapshot" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #a855f7',paddingLeft:12}}>7. How CamperSnapshot Sync Works</h2>
          <p style={{color:'#d1d5db',fontSize:14,lineHeight:1.7,margin:'0 0 16px'}}>
            Every time you tap Present or Absent, your mark is <strong style={{color:'white'}}>instantly pushed</strong> to Camper Snapshot — the central system all staff use.
          </p>
          <div style={{background:'#1f2937',borderRadius:10,padding:16,border:'1px solid #374151',marginBottom:16}}>
            <h3 style={{color:'#a855f7',fontSize:13,fontWeight:700,margin:'0 0 12px'}}>THE SYNC FLOW</h3>
            <div style={{display:'flex',flexDirection:'column',gap:10}}>
              <div style={{display:'flex',gap:10,alignItems:'flex-start'}}>
                <div style={{width:28,height:28,borderRadius:'50%',background:'#2563eb',color:'white',fontSize:12,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>1</div>
                <div style={{color:'#d1d5db',fontSize:13,lineHeight:1.5}}>You tap Present or Absent on a camper</div>
              </div>
              <div style={{borderLeft:'2px dashed #374151',marginLeft:14,height:8}}></div>
              <div style={{display:'flex',gap:10,alignItems:'flex-start'}}>
                <div style={{width:28,height:28,borderRadius:'50%',background:'#2563eb',color:'white',fontSize:12,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>2</div>
                <div style={{color:'#d1d5db',fontSize:13,lineHeight:1.5}}>This app saves it locally AND pushes it to Camper Snapshot in real time</div>
              </div>
              <div style={{borderLeft:'2px dashed #374151',marginLeft:14,height:8}}></div>
              <div style={{display:'flex',gap:10,alignItems:'flex-start'}}>
                <div style={{width:28,height:28,borderRadius:'50%',background:'#2563eb',color:'white',fontSize:12,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>3</div>
                <div style={{color:'#d1d5db',fontSize:13,lineHeight:1.5}}>Camper Snapshot compares your mark with Group Attendance</div>
              </div>
              <div style={{borderLeft:'2px dashed #374151',marginLeft:14,height:8}}></div>
              <div style={{display:'flex',gap:10,alignItems:'flex-start'}}>
                <div style={{width:28,height:28,borderRadius:'50%',background:'#22c55e',color:'white',fontSize:12,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>4</div>
                <div style={{color:'#d1d5db',fontSize:13,lineHeight:1.5}}><strong style={{color:'#4ade80'}}>Match</strong> = confirmed, no action needed</div>
              </div>
              <div style={{borderLeft:'2px dashed #374151',marginLeft:14,height:8}}></div>
              <div style={{display:'flex',gap:10,alignItems:'flex-start'}}>
                <div style={{width:28,height:28,borderRadius:'50%',background:'#dc2626',color:'white',fontSize:12,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>5</div>
                <div style={{color:'#d1d5db',fontSize:13,lineHeight:1.5}}><strong style={{color:'#f87171'}}>Conflict</strong> = bus says one thing, group says another → supervisor resolves</div>
              </div>
            </div>
          </div>
          <div style={{background:'#1c1917',border:'1px solid #f59e0b',borderRadius:8,padding:12}}>
            <div style={{color:'#fcd34d',fontSize:13,lineHeight:1.7}}>
              <strong>This is why marking Absent matters:</strong> If you skip a kid (leave as Unmarked), the system has no bus data for them. That creates an "unknown" state that supervisors must manually investigate. Marking them Absent = clean data = no false alarms.
            </div>
          </div>
        </div>

        {/* Section 8: Troubleshooting */}
        <div id="help-fix" style={{marginBottom:32}}>
          <h2 style={{color:'white',fontSize:18,fontWeight:700,margin:'0 0 12px',borderLeft:'4px solid #6b7280',paddingLeft:12}}>8. Something Not Working?</h2>
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            {[
              { q: "Page won't load", a: "Check your phone's WiFi or cell data. Try refreshing the page." },
              { q: "Wrong bus number", a: "Tap the logout arrow (top-right) to go back and re-enter your bus number." },
              { q: "A camper's name is missing", a: "They may have been reassigned to a different bus. Tell the front desk when you arrive." },
              { q: "Buttons not responding", a: "Pull down to refresh on mobile, or hard-refresh (Ctrl+Shift+R). If still broken, contact Brian Stein." },
              { q: "GPS badge is red", a: "Tap the Retry button. If that doesn't work, check your phone settings (see GPS section above)." },
              { q: "I missed the 9:30 deadline", a: "Contact the main office immediately. An admin can temporarily unlock attendance." },
            ].map((item, i) => (
              <div key={i} style={{background:'#1f2937',borderRadius:8,padding:12,border:'1px solid #374151'}}>
                <div style={{color:'white',fontSize:13,fontWeight:600,marginBottom:4}}>{item.q}</div>
                <div style={{color:'#9ca3af',fontSize:13}}>{item.a}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{textAlign:'center',padding:'20px 0 40px',borderTop:'1px solid #374151'}}>
          <p style={{color:'#6b7280',fontSize:12,margin:0}}>Rolling River Day Camp — Bus Mapping App</p>
          <p style={{color:'#6b7280',fontSize:11,margin:'4px 0 0'}}>Something broken? Contact Brian Stein</p>
        </div>
      </div>
    </div>
  );
}
