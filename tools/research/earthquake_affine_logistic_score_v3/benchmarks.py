"""Fixed invented distributions; never reads research arrays or model files."""
CASES=[
    dict(name='normal',pi=[.2]*5,mu=[0.]*5,sigma=[1.]*5,affine=[],target=0.),
    dict(name='moderate_19',pi=[.2]*5,mu=[3.,4.,5.,6.,7.],sigma=[.5,.8,1.,1.2,1.5],affine=[[.1*(-1)**j,.2*(-1)**j]for j in range(19)],target=6.),
    dict(name='multimodal',pi=[.1,.2,.3,.15,.25],mu=[-2.,-1.,0.,2.,3.],sigma=[.4,.5,1.,2.,.2],affine=[[.2,.6],[-.5,-.3]],target=.5),
    dict(name='tail',pi=[.001,.009,.09,.3,.6],mu=[-5.,0.,4.,8.,12.],sigma=[.05,.2,.8,1.,2.],affine=[[2.,-.2],[-2.,.4]],target=15.),
    dict(name='broad_narrow',pi=[.2]*5,mu=[-20.,-5.,0.,5.,30.],sigma=[.05,.1,2.,10.,.2],affine=[[0.,.1]],target=4.),
    dict(name='sharp_20',pi=[.2]*5,mu=[0.]*5,sigma=[1.]*5,affine=[[0.,20.]],target=1.),
    dict(name='far_label',pi=[.2]*5,mu=[5.]*5,sigma=[.05]*5,affine=[[0.,.01]],target=30.),
    dict(name='rare_far_symmetric',pi=[1e-9,.2,.599999998,.2,1e-9],mu=[-10000.,-1.,0.,1.,10000.],sigma=[.1,1.,1.,1.,.1],affine=[],target=0.)
]
